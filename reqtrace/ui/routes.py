# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
REST API Routes (/api/v1) and Launch Handler for ReqTrace UI.
Exposes typed endpoints for executive audit metrics, partitioned diagnostic reasons,
traceability matrix grid, candidate review queue, evidence inspection,
workspace lifecycle management, drag-and-drop file ingestion, unified exports,
and print-ready audit reports.
"""

import html
import json
import secrets
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from reqtrace.analysis.coordinator import AnalysisCoordinator
from reqtrace.analysis.review_store import ReviewStore
from reqtrace.analysis.status import (
    RequirementStatusResult,
    UnverifiedReasonCode,
    WorkspaceStatusReport,
    evaluate_workspace_status,
)
from reqtrace.models.export import ExportFormat, ExportRequest, ExportResult
from reqtrace.models.requirement import Requirement, VerificationMethod
from reqtrace.models.test_artifact import TestArtifact
from reqtrace.models.trace_link import (
    LinkConfidence,
    ReviewEvent,
    ReviewStatus,
    TraceLink,
    VerificationStatus,
)
from reqtrace.models.workspace import ProjectMetadata, WorkspaceInfo, WorkspaceManifest
from reqtrace.reports.exporter import ExportManager
from reqtrace.ui.security import (
    SessionStore,
    TicketStore,
    normalize_ticket_input,
    validate_workspace_path,
)
from reqtrace.workspace.manager import WorkspaceManager


# --- Request DTOs ---

class CreateWorkspaceRequest(BaseModel):
    path: str
    project_name: str
    target_standard: Optional[str] = "DO-178C DAL B"
    spec_version: Optional[str] = "1.0"
    baseline_id: Optional[str] = "BASELINE-001"


class OpenWorkspaceRequest(BaseModel):
    path: str


class ReviewSubmissionRequest(BaseModel):
    req_id: str
    test_id: Optional[str] = None
    status: str  # "approved", "rejected", "waived_analysis"
    reviewer: str = "Local Engineer"
    comment: Optional[str] = None
    reference_doc: Optional[str] = None


class CandidateActionRequest(BaseModel):
    action: str  # "approve" or "reject"
    req_id: str
    test_id: str
    comment: Optional[str] = None
    reviewer: Optional[str] = "Local Engineer"


class WorkspaceDataLoader:
    """
    Backward-compatible data loader for ReqTrace workspace artifacts,
    delegating to AnalysisCoordinator for caching and performance optimization.
    """

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.coordinator = AnalysisCoordinator(self.workspace_root)
        self.review_store = self.coordinator.review_store

    def load_requirements(self) -> List[Requirement]:
        return self.coordinator.get_requirements()

    def load_tests(self) -> List[TestArtifact]:
        return self.coordinator.get_tests()

    def load_links(self) -> List[TraceLink]:
        return self.coordinator.get_links()

    def evaluate_status(self) -> WorkspaceStatusReport:
        return self.coordinator.get_status()


def create_api_router(
    workspace_root: Path,
    ticket_store: TicketStore,
    session_store: SessionStore,
    cookie_name: str,
    coordinator: Optional[AnalysisCoordinator] = None,
    operator_secret: Optional[str] = None,
) -> APIRouter:
    router = APIRouter()
    coord = coordinator or AnalysisCoordinator(workspace_root)
    ws_mgr = coord.workspace_manager

    # --- Launch & Auth Endpoint ---

    @router.get("/login", include_in_schema=False)
    def exchange_launch_ticket(ticket: Optional[str] = None):
        """
        Exchanges a single-use launch ticket for an HttpOnly session cookie,
        redirecting immediately to the clean root URL.
        """
        normalized_ticket = normalize_ticket_input(ticket)
        if not normalized_ticket or not ticket_store.consume_ticket(normalized_ticket):
            return HTMLResponse(
                content=f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>ReqTrace - Launch Ticket Expired or Invalid</title>
  <link rel="stylesheet" href="/app.css" />
</head>
<body class="auth-gateway-body">
  <div class="auth-gateway-card">
    <h1 class="auth-gateway-error">Launch Ticket Expired or Invalid</h1>
    <p>Launch tickets are single-use and expire after {ticket_store.timeout_sec} seconds for security.</p>
    <hr class="auth-gateway-divider" />
    <form action="/login" method="GET">
      <input type="text" name="ticket" class="auth-gateway-input" placeholder="Paste a fresh Ticket or full Launch URL" required />
      <button type="submit" class="auth-gateway-submit">Sign In</button>
    </form>
    <div class="auth-gateway-steps">
      <div class="auth-gateway-steps-title">How to get a fresh launch ticket:</div>
      <ul class="auth-gateway-list">
        <li><strong>Docker Desktop / CLI (No Restart Needed):</strong> Run <code>docker exec reqtrace-cockpit reqtrace ticket</code></li>
        <li><strong>Automated Helper:</strong> Run <code>.\\docker-run.ps1 -Detach</code> or <code>./docker-run.sh -d</code></li>
        <li><strong>Local Terminal:</strong> Run <code>reqtrace ticket</code> or restart <code>reqtrace ui</code></li>
      </ul>
    </div>
    <a href="/" class="auth-gateway-back">Back to Authentication Gateway</a>
  </div>
</body>
</html>""",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        session_id = session_store.create_session()
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key=cookie_name,
            value=session_id,
            httponly=True,
            samesite="strict",
            path="/",
        )
        return response

    @router.post("/internal/ticket", include_in_schema=False)
    def mint_operator_ticket(
        x_reqtrace_operator: Optional[str] = Header(default=None, alias="X-ReqTrace-Operator"),
    ) -> Dict[str, Any]:
        """
        Internal OS-operator endpoint used by `reqtrace ticket` / `docker exec`
        to generate a fresh single-use ticket for a running server instance.
        """
        if (
            not operator_secret
            or not x_reqtrace_operator
            or not secrets.compare_digest(x_reqtrace_operator, operator_secret)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Valid operator secret required.",
            )
        fresh_ticket = ticket_store.generate_ticket()
        return {
            "ticket": fresh_ticket,
            "timeout_sec": ticket_store.timeout_sec,
        }

    # --- Workspace Lifecycle Endpoints ---

    @router.get("/api/v1/workspaces")
    def list_recent_workspaces() -> List[Dict[str, Any]]:
        """Lists recent workspaces tracked in ~/.reqtrace/workspaces.json."""
        return [w.model_dump() for w in ws_mgr.get_recent_workspaces()]

    @router.post("/api/v1/workspaces")
    def create_workspace(body: CreateWorkspaceRequest) -> Dict[str, Any]:
        """
        Initializes a ReqTrace workspace inside an existing directory (Option B).
        Fails with HTTP 400 if directory does not exist.
        """
        try:
            manifest, metadata = ws_mgr.init_workspace(
                path=body.path,
                project_name=body.project_name,
                target_standard=body.target_standard or "DO-178C DAL B",
                spec_version=body.spec_version or "1.0",
                baseline_id=body.baseline_id or "BASELINE-001",
            )
            coord.switch_workspace(Path(body.path))
            return {
                "status": "ok",
                "workspace": str(coord.workspace_root),
                "manifest": manifest.model_dump(),
                "project": metadata.model_dump(),
            }
        except FileNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.post("/api/v1/workspaces/open")
    def open_workspace(body: OpenWorkspaceRequest) -> Dict[str, Any]:
        """
        Opens an existing workspace directory (Option B).
        Fails with HTTP 400 if directory does not exist.
        """
        try:
            manifest, metadata = ws_mgr.open_workspace(path=body.path)
            coord.switch_workspace(Path(body.path))
            return {
                "status": "ok",
                "workspace": str(coord.workspace_root),
                "manifest": manifest.model_dump(),
                "project": metadata.model_dump(),
            }
        except FileNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.get("/api/v1/workspace/current")
    def get_current_workspace() -> Dict[str, Any]:
        """Returns the active workspace directory, manifest, and project metadata."""
        return {
            "workspace": str(coord.workspace_root),
            "manifest": coord.manifest.model_dump(),
            "project": coord.project_meta.model_dump(),
        }

    @router.patch("/api/v1/project")
    def update_project(updates: Dict[str, Any]) -> Dict[str, Any]:
        """Updates editable project metadata fields."""
        updated = ws_mgr.update_project_metadata(coord.workspace_root, updates)
        coord.project_meta = updated
        return updated.model_dump()

    # --- Ingestion Wizard Endpoints ---

    def _inspect_xml_root_tag(xml_path: Path) -> str:
        """Returns the lowercase local root tag name of an XML file safely."""
        try:
            import defusedxml.ElementTree as ET
        except ImportError:
            import xml.etree.ElementTree as ET
        tree = ET.parse(str(xml_path))
        root_tag = tree.getroot().tag
        return root_tag.split("}")[-1].lower()

    def _stage_uploaded_file(
        file: UploadFile,
        allowed_exts: Set[str],
        prefix: str,
        default_name: str,
        kind_label: str,
    ) -> Tuple[Path, Path, str, str]:
        """Validates extension/size and writes upload to an isolated temp directory."""
        safe_name = Path(file.filename or default_name).name
        ext = Path(safe_name).suffix.lower()
        if ext not in allowed_exts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported {kind_label} file extension: '{ext}'. Allowed: {', '.join(sorted(allowed_exts))}",
            )

        contents = file.file.read()
        if len(contents) > 25 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds maximum permitted limit (25MB).",
            )

        tmp_dir = coord.workspace_root / ".reqtrace" / "tmp"
        upload_dir = tmp_dir / f"{prefix}_{uuid.uuid4().hex[:8]}"
        upload_dir.mkdir(parents=True, exist_ok=True)
        temp_file = upload_dir / safe_name
        with open(temp_file, "wb") as f:
            f.write(contents)
        return upload_dir, temp_file, safe_name, ext

    @router.post("/api/v1/ingest/spec")
    def ingest_specification(file: UploadFile = File(...)) -> Dict[str, Any]:
        """
        Uploads and parses a requirement specification (.reqif, .xml, .csv, .docx).
        Enforces 25MB limit, validates payload type, and persists atomically.
        """
        upload_dir, temp_file, safe_name, ext = _stage_uploaded_file(
            file=file,
            allowed_exts={".reqif", ".xml", ".csv", ".docx"},
            prefix="spec",
            default_name="spec.reqif",
            kind_label="specification",
        )
        try:
            parsed_reqs: List[Requirement] = []
            if ext in {".reqif", ".xml"}:
                root_local = _inspect_xml_root_tag(temp_file)
                if root_local in {"testsuites", "testsuite"}:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"'{safe_name}' is a JUnit test execution report (<{root_local}>), "
                            "not a Requirements Specification. Drop it in 'Test Artifacts & Verdicts' on the right."
                        ),
                    )
                from reqtrace.parsers.reqif_parser import ReqIFParser
                parsed_reqs = ReqIFParser().parse(temp_file)
            elif ext == ".csv":
                from reqtrace.parsers.csv_parser import CSVParser
                parsed_reqs = CSVParser().parse(temp_file)
            elif ext == ".docx":
                from reqtrace.parsers.docx_parser import DocxSpecificationParser
                parsed_reqs = DocxSpecificationParser().parse(temp_file)

            if not parsed_reqs:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"No requirements were extracted from '{safe_name}'. "
                        "Verify the file format/columns; existing workspace requirements were preserved."
                    ),
                )

            serialized_reqs = [r.model_dump() for r in parsed_reqs]
            reqs_path = coord.workspace_root / coord.manifest.requirements_file
            with open(reqs_path, "w", encoding="utf-8") as f:
                json.dump(serialized_reqs, f, indent=2)

            coord.invalidate_requirements()
            status_report = coord.get_status()

            normative_count = sum(1 for r in parsed_reqs if r.is_normative)
            return {
                "status": "ok",
                "filename": file.filename,
                "total_requirements": len(parsed_reqs),
                "normative_requirements": normative_count,
                "non_normative_headings": len(parsed_reqs) - normative_count,
                "summary": status_report.model_dump(),
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse specification '{safe_name}': {exc}",
            )
        finally:
            shutil.rmtree(upload_dir, ignore_errors=True)

    @router.post("/api/v1/ingest/tests")
    def ingest_tests(file: UploadFile = File(...)) -> Dict[str, Any]:
        """
        Uploads and scans test artifacts (.xml JUnit reports or test code: .py, .cpp, .cc, .c, .h, .feature).
        """
        upload_dir, temp_file, safe_name, ext = _stage_uploaded_file(
            file=file,
            allowed_exts={".xml", ".py", ".cpp", ".cc", ".cxx", ".c", ".h", ".feature"},
            prefix="test",
            default_name="tests.py",
            kind_label="test",
        )
        try:
            parsed_tests: List[TestArtifact] = []
            attached_verdicts: Optional[int] = None

            if ext == ".xml":
                root_local = _inspect_xml_root_tag(temp_file)
                if root_local == "req-if":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"'{safe_name}' is a ReqIF Requirements Specification, not a JUnit report. "
                            "Drop it in 'Requirements Specification' on the left."
                        ),
                    )
                from reqtrace.parsers.junit_parser import JUnitParser
                junit_parser = JUnitParser()
                verdicts = junit_parser.parse(temp_file)
                if not verdicts:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"No <testcase> verdicts were found in '{safe_name}'. Existing tests were preserved.",
                    )

                existing_tests = coord.get_tests()
                has_code_tests = any(t.framework != "junit" for t in existing_tests)
                if existing_tests and has_code_tests:
                    parsed_tests = junit_parser.attach_verdicts(existing_tests, temp_file)
                    matched = sum(
                        1 for art in parsed_tests
                        if (art.id in verdicts or art.id.split("::")[-1] in verdicts)
                    )
                    attached_verdicts = matched
                else:
                    seen_cases: set = set()
                    for res in verdicts.values():
                        case_key = (res.classname, res.name)
                        if case_key in seen_cases:
                            continue
                        seen_cases.add(case_key)
                        test_id = f"{res.classname}::{res.name}" if res.classname else res.name
                        parsed_tests.append(
                            TestArtifact(
                                id=test_id,
                                file_path=safe_name,
                                line_start=1,
                                line_end=1,
                                framework="junit",
                                execution_status=res.status,
                                execution_time_sec=res.time_sec,
                            )
                        )
            elif ext == ".py":
                from reqtrace.parsers.code.python_ast import PythonASTParser
                parsed_tests = PythonASTParser().parse_file(temp_file)
            elif ext in {".cpp", ".cc", ".cxx", ".c", ".h"}:
                from reqtrace.parsers.code.cpp_harness import CppHarnessParser
                parsed_tests = CppHarnessParser().parse_file(temp_file)
            elif ext == ".feature":
                from reqtrace.parsers.code.gherkin import GherkinFeatureParser
                parsed_tests = GherkinFeatureParser().parse_file(temp_file)

            if not parsed_tests:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No test cases were extracted from '{safe_name}'. Existing test artifacts were preserved.",
                )

            if ext != ".xml":
                for art in parsed_tests:
                    art.file_path = safe_name

            serialized_tests = [t.model_dump() for t in parsed_tests]
            tests_path = coord.workspace_root / coord.manifest.tests_file
            with open(tests_path, "w", encoding="utf-8") as f:
                json.dump(serialized_tests, f, indent=2)

            coord.invalidate_tests()
            status_report = coord.get_status()

            response_payload: Dict[str, Any] = {
                "status": "ok",
                "filename": file.filename,
                "total_tests": len(parsed_tests),
                "summary": status_report.model_dump(),
            }
            if attached_verdicts is not None:
                response_payload["attached_verdicts"] = attached_verdicts
            return response_payload
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse test file '{safe_name}': {exc}",
            )
        finally:
            shutil.rmtree(upload_dir, ignore_errors=True)

    # --- Review Sign-Off & Candidate Triage Endpoints ---

    @router.post("/api/v1/reviews")
    def submit_review(body: ReviewSubmissionRequest) -> Dict[str, Any]:
        """
        Records human review decisions (APPROVED, REJECTED, WAIVED_ANALYSIS).
        Enforces mandatory comments on rejection and mandatory reference docs on waivers.
        """
        status_clean = body.status.lower().strip()
        if status_clean not in {"approved", "rejected", "waived_analysis"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid review status: '{body.status}'. Must be 'approved', 'rejected', or 'waived_analysis'.",
            )
        if status_clean == "rejected" and (not body.comment or len(body.comment.strip()) < 5):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A comment explaining the rejection (minimum 5 characters) is mandatory.",
            )
        if status_clean == "waived_analysis" and (not body.reference_doc or len(body.reference_doc.strip()) == 0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A reference document identifier is mandatory when waiving non-test verification.",
            )

        reqs = coord.get_requirements()
        current_req = next((r for r in reqs if r.id == body.req_id), None)
        req_hash = current_req.sha256 if current_req else None

        event = ReviewEvent(
            req_id=body.req_id,
            test_id=body.test_id,
            status=ReviewStatus(status_clean),
            reviewed_by=body.reviewer,
            comment=body.comment,
            reference_doc=body.reference_doc,
            req_content_hash=req_hash,
            req_sha256_at_review=req_hash,
        )
        report = coord.record_review(event)
        return {
            "status": "ok",
            "event_id": event.event_id,
            "req_id": event.req_id,
            "summary": report.model_dump(),
        }

    @router.post("/api/v1/candidates/action")
    def candidate_action(body: CandidateActionRequest) -> Dict[str, Any]:
        """
        Promotes (approve) or rejects (reject) a heuristic candidate verification link.
        """
        try:
            report = coord.record_candidate_action(
                action=body.action,
                req_id=body.req_id,
                test_id=body.test_id,
                comment=body.comment,
                reviewer=body.reviewer or "Local Engineer",
            )
            return {
                "status": "ok",
                "action": body.action,
                "req_id": body.req_id,
                "test_id": body.test_id,
                "summary": report.model_dump(),
            }
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.get("/api/v1/reviews/{req_id}")
    def get_requirement_review_history(req_id: str) -> Dict[str, Any]:
        """Returns the full chronological audit history of review events for a requirement."""
        events = coord.review_store.load_events()
        req_events = [e.model_dump() for e in events if e.req_id == req_id]
        return {"req_id": req_id, "events": req_events}

    # --- Unified Export Service Endpoints ---

    @router.post("/api/v1/export")
    def create_export(request: ExportRequest) -> Dict[str, Any]:
        """Generates an export package (CSV, ReqIF, HTML, JSON) via ExportManager."""
        export_mgr = ExportManager(coord.workspace_root)
        result = export_mgr.export(request)
        return result.model_dump()

    @router.get("/api/v1/export/{export_format}")
    def download_export_direct(export_format: str):
        """Streams a generated export deliverable directly to the browser."""
        fmt_clean = export_format.lower().strip()
        if fmt_clean not in {"csv", "reqif", "html", "json"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported export format '{export_format}'. Allowed: csv, reqif, html, json",
            )

        req = ExportRequest(format=ExportFormat(fmt_clean))
        export_mgr = ExportManager(coord.workspace_root)
        result = export_mgr.export(req)

        media_types = {
            "csv": "text/csv",
            "reqif": "application/xml",
            "html": "text/html",
            "json": "application/json",
        }
        return FileResponse(
            path=result.file_path,
            filename=result.filename,
            media_type=media_types.get(fmt_clean, "application/octet-stream"),
        )

    # --- Print View Endpoint ---

    @router.get("/print", include_in_schema=False)
    def print_view():
        """
        Renders a non-virtualized, paginated HTML matrix specifically formatted
        with @media print CSS for clean auditor PDF/paper generation.
        """
        reqs = coord.get_requirements()
        tests = coord.get_tests()
        links = coord.get_links()
        status_report = coord.get_status()
        project = coord.project_meta

        test_map = {t.id: t for t in tests}
        links_by_req: Dict[str, List[TraceLink]] = {}
        for l in links:
            links_by_req.setdefault(l.req_id, []).append(l)

        rows_html = []
        for r in reqs:
            res = status_report.requirement_results.get(r.id)
            r_links = links_by_req.get(r.id, [])

            v_badge_color = {
                "verified": "#10b981",
                "linked_passing": "#3b82f6",
                "unverified_gap": "#f43f5e",
            }.get(res.verification_status.value if res else "unverified_gap", "#64748b")

            linked_tests_str = "<br>".join([
                f"<code>{html.escape(l.test_id)}</code> "
                f"<span style='color:{'#10b981' if l.is_verified else '#f43f5e'}'>({l.confidence.value})</span>"
                for l in r_links
            ]) if r_links else "<em style='color:#94a3b8'>No tests linked</em>"

            evidence_str = "<br>".join([
                f"<code>{html.escape(l.evidence_span)}</code>"
                for l in r_links if l.evidence_span
            ]) or "—"

            review_str = "<br>".join([
                f"{l.review_status.value.upper()} by {html.escape(l.reviewed_by or 'N/A')}"
                for l in r_links if l.review_status != ReviewStatus.PENDING
            ]) or "Unreviewed"

            rows_html.append(f"""
            <tr>
              <td><strong>{html.escape(r.id)}</strong></td>
              <td>{html.escape(r.title)}</td>
              <td>{r.level.value} / {'Normative' if r.is_normative else 'Informative'}</td>
              <td><span style='background:{v_badge_color};color:white;padding:2px 6px;border-radius:4px;font-size:8pt;'>
                {res.verification_status.value.upper() if res else 'GAP'}
              </span></td>
              <td>{linked_tests_str}</td>
              <td>{evidence_str}</td>
              <td>{review_str}</td>
            </tr>
            """)

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>ReqTrace Print Matrix - {html.escape(project.project_name)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 9pt; color: #1e293b; margin: 1.5cm; }}
    h1 {{ font-size: 16pt; margin-bottom: 4px; }}
    .meta-bar {{ margin-bottom: 16px; font-size: 9pt; color: #475569; }}
    .kpi-row {{ display: flex; gap: 16px; margin-bottom: 20px; }}
    .kpi {{ border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 12px; }}
    .kpi-value {{ font-size: 14pt; font-weight: bold; color: #0f172a; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 8.5pt; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f8fafc; font-weight: 600; }}
    code {{ font-family: monospace; font-size: 8pt; }}
    @media print {{
      body {{ margin: 0; }}
      .no-print {{ display: none !important; }}
      tr {{ page-break-inside: avoid; }}
      thead {{ display: table-header-group; }}
    }}
  </style>
</head>
<body>
  <div class="no-print" style="margin-bottom: 16px;">
    <button onclick="window.print()" style="padding: 8px 16px; background: #2563eb; color: white; border: none; border-radius: 4px; cursor: pointer;">
      🖨️ Print / Save as PDF
    </button>
  </div>
  <h1>{html.escape(project.project_name)} — Verification Traceability Matrix</h1>
  <div class="meta-bar">
    <strong>Standard:</strong> {html.escape(project.target_standard or 'DO-178C')} &nbsp;|&nbsp;
    <strong>Baseline:</strong> {html.escape(project.baseline_id or 'CURRENT')} &nbsp;|&nbsp;
    <strong>Spec Version:</strong> {html.escape(project.spec_version or '1.0')} &nbsp;|&nbsp;
    <strong>Generated:</strong> {project.updated_at}
  </div>
  <div class="kpi-row">
    <div class="kpi"><div class="kpi-label">Total Normative</div><div class="kpi-value">{status_report.total_normative}</div></div>
    <div class="kpi"><div class="kpi-label">Audit Verified</div><div class="kpi-value">{status_report.verified_count} ({status_report.audit_verified_coverage_pct}%)</div></div>
    <div class="kpi"><div class="kpi-label">Linked Passing</div><div class="kpi-value">{status_report.linked_passing_count}</div></div>
    <div class="kpi"><div class="kpi-label">Unverified Gaps</div><div class="kpi-value">{status_report.unverified_gaps}</div></div>
  </div>
  <table>
    <thead>
      <tr>
        <th style="width: 12%;">Req ID</th>
        <th style="width: 22%;">Title</th>
        <th style="width: 10%;">Level / Class</th>
        <th style="width: 10%;">Status</th>
        <th style="width: 20%;">Linked Tests</th>
        <th style="width: 14%;">Assertion Evidence</th>
        <th style="width: 12%;">Human Review</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>
</body>
</html>
"""
        return HTMLResponse(content=html_content)

    # --- Existing Operational Endpoints ---

    @router.get("/api/v1/status")
    def get_server_status() -> Dict[str, Any]:
        """Server health, version, and active workspace info."""
        return {
            "status": "ok",
            "version": "0.2.0",
            "workspace": str(coord.workspace_root),
            "project_name": coord.project_meta.project_name,
            "baseline_id": coord.project_meta.baseline_id,
        }

    @router.get("/api/v1/summary")
    def get_audit_summary() -> WorkspaceStatusReport:
        """Executive audit dashboard metrics."""
        return coord.get_status()

    @router.get("/api/v1/reasons")
    def get_unverified_reasons() -> Dict[str, Any]:
        """Partitioned diagnostic unverified reason counts."""
        report = coord.get_status()
        return {
            "total_normative": report.total_normative,
            "verified_count": report.verified_count,
            "linked_passing_count": report.linked_passing_count,
            "unverified_gaps": report.unverified_gaps,
            "gap_reasons": {k.value: v for k, v in report.gap_reasons.items()},
            "rogue_tests_unlinked": report.rogue_tests_unlinked,
            "audit_verified_coverage_pct": report.audit_verified_coverage_pct,
            "engineering_pass_coverage_pct": report.engineering_pass_coverage_pct,
        }

    @router.get("/api/v1/matrix")
    def get_matrix_rows(
        search: Optional[str] = Query(None, description="Search text in ID, title, or test"),
        status_filter: Optional[str] = Query(None, alias="status"),
        method_filter: Optional[str] = Query(None, alias="method"),
        level_filter: Optional[str] = Query(None, alias="level"),
    ) -> Dict[str, Any]:
        """
        Full traceability matrix with two-axis statuses, affirmative assertions,
        and linked test artifact details.
        """
        reqs = coord.get_requirements()
        tests = coord.get_tests()
        links = coord.get_links()

        test_map = {t.id: t for t in tests}
        report = coord.get_status()

        items: List[Dict[str, Any]] = []
        for req in reqs:
            res = report.requirement_results.get(req.id)
            req_links = [l for l in links if l.req_id == req.id]

            # Filters
            if isinstance(status_filter, str) and status_filter and res:
                if status_filter.lower() != res.verification_status.value.lower():
                    continue
            if isinstance(method_filter, str) and method_filter:
                if method_filter.lower() != req.verification_method.value.lower():
                    continue
            if isinstance(level_filter, str) and level_filter:
                if level_filter.lower() != req.level.value.lower():
                    continue

            # Text Search
            if isinstance(search, str) and search:
                term = search.lower()
                matches_req = (
                    term in req.id.lower()
                    or term in req.title.lower()
                    or term in req.description.lower()
                )
                matches_test = any(term in l.test_id.lower() for l in req_links)
                if not (matches_req or matches_test):
                    continue

            linked_test_details = []
            for link in req_links:
                t = test_map.get(link.test_id)
                linked_test_details.append({
                    "test_id": link.test_id,
                    "file_path": t.file_path if t else "",
                    "line_start": t.line_start if t else 0,
                    "line_end": t.line_end if t else 0,
                    "verdict": t.execution_status.value if t else "unexecuted",
                    "confidence": link.confidence.value,
                    "is_candidate": link.is_candidate,
                    "review_status": link.review_status.value,
                    "evidence_span": link.evidence_span,
                    "is_stale": link.is_stale,
                    "is_execution_stale": link.is_execution_stale,
                    "match_strategy": link.match_strategy,
                    "match_reason": link.match_reason,
                })

            items.append({
                "id": req.id,
                "title": req.title,
                "description": req.description,
                "is_normative": req.is_normative,
                "level": req.level.value,
                "verification_method": req.verification_method.value,
                "verification_status": res.verification_status.value if res else "unverified_gap",
                "primary_reason": res.primary_reason.value if (res and res.primary_reason) else None,
                "all_reasons": [r.value for r in res.all_reasons] if res else [],
                "linked_tests": linked_test_details,
            })

        return {"items": items, "total": len(items)}

    @router.get("/api/v1/candidates")
    def get_candidate_links() -> List[Dict[str, Any]]:
        """
        Returns heuristic and fuzzy link candidates awaiting human review.
        Includes match_strategy provenance.
        """
        reqs = coord.get_requirements()
        tests = coord.get_tests()
        links = coord.get_links()

        req_map = {r.id: r for r in reqs}
        test_map = {t.id: t for t in tests}

        candidates: List[Dict[str, Any]] = []
        for l in links:
            if l.is_candidate and l.review_status in (ReviewStatus.PENDING, ReviewStatus.UNREVIEWED):
                req = req_map.get(l.req_id)
                t = test_map.get(l.test_id)
                candidates.append({
                    "req_id": l.req_id,
                    "req_title": req.title if req else "",
                    "test_id": l.test_id,
                    "test_file": t.file_path if t else "",
                    "confidence": l.confidence.value,
                    "confidence_score": l.confidence_score,
                    "evidence_span": l.evidence_span,
                    "justification": l.justification,
                    "match_strategy": l.match_strategy or "heuristic",
                    "match_reason": l.match_reason or "Automated match proposal",
                })
        return candidates

    @router.get("/api/v1/evidence/{req_id}")
    def get_evidence_details(req_id: str, test_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Detailed evidence inspector: verbatim clause, test AST snippet, line bounds,
        affirmative assertions, and execution staleness flag.
        """
        reqs = coord.get_requirements()
        tests = coord.get_tests()
        links = coord.get_links()

        req = next((r for r in reqs if r.id == req_id), None)
        if not req:
            raise HTTPException(status_code=404, detail=f"Requirement not found: {req_id}")

        req_links = [l for l in links if l.req_id == req_id]
        chosen_link = (
            next((l for l in req_links if l.test_id == test_id), req_links[0])
            if req_links
            else None
        )

        test = next((t for t in tests if t.id == chosen_link.test_id), None) if chosen_link else None
        path_line = f"{test.file_path}:{test.line_start}" if test else ""

        return {
            "req": req.model_dump(),
            "test": test.model_dump() if test else None,
            "link": chosen_link.model_dump() if chosen_link else None,
            "path_line": path_line,
        }

    return router
