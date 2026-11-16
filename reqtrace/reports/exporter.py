# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unified Export Service Layer for ReqTrace.
Provides centralized generation of auditor deliverables (CSV, ReqIF, HTML, JSON),
attaching formal project metadata, and calculating tamper-evident SHA-256 hashes.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from reqtrace.analysis.status import WorkspaceStatusReport, evaluate_workspace_status
from reqtrace.analysis.review_store import ReviewStore
from reqtrace.models.export import ExportFormat, ExportRequest, ExportResult
from reqtrace.models.requirement import Requirement
from reqtrace.models.test_artifact import TestArtifact
from reqtrace.models.trace_link import TraceLink
from reqtrace.models.workspace import ProjectMetadata, WorkspaceManifest
from reqtrace.reports.csv_exporter import CSVRTMExporter
from reqtrace.reports.html_report import HTMLReportGenerator
from reqtrace.reports.reqif_exporter import ReqIFExporter


class ExportManager:
    """
    Centralized service layer for auditor deliverables and interchange packages.
    """

    def __init__(self, workspace_root: Path | str) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.csv_exporter = CSVRTMExporter()
        self.reqif_exporter = ReqIFExporter()
        self.html_exporter = HTMLReportGenerator()

    def _compute_sha256(self, file_path: Path) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _get_project_metadata(self) -> ProjectMetadata:
        project_file = self.workspace_root / ".reqtrace" / "project.json"
        if project_file.exists():
            try:
                with open(project_file, "r", encoding="utf-8") as f:
                    return ProjectMetadata.model_validate_json(f.read())
            except Exception:
                pass
        now_str = datetime.now(timezone.utc).isoformat()
        return ProjectMetadata(
            project_name=self.workspace_root.name,
            created_at=now_str,
            updated_at=now_str,
        )

    def _get_workspace_manifest(self) -> WorkspaceManifest:
        manifest_file = self.workspace_root / ".reqtrace" / "workspace.json"
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    return WorkspaceManifest.model_validate_json(f.read())
            except Exception:
                pass
        return WorkspaceManifest()

    def _load_data(self) -> tuple[List[Requirement], List[TestArtifact], List[TraceLink], ReviewStore]:
        manifest = self._get_workspace_manifest()

        reqs_path = self.workspace_root / manifest.requirements_file
        reqs: List[Requirement] = []
        if reqs_path.exists():
            try:
                with open(reqs_path, "r", encoding="utf-8") as f:
                    reqs = [Requirement.model_validate(i) for i in json.load(f)]
            except Exception:
                pass

        tests_path = self.workspace_root / manifest.tests_file
        tests: List[TestArtifact] = []
        if tests_path.exists():
            try:
                with open(tests_path, "r", encoding="utf-8") as f:
                    tests = [TestArtifact.model_validate(i) for i in json.load(f)]
            except Exception:
                pass

        links_path = self.workspace_root / "links.json"
        links: List[TraceLink] = []
        if links_path.exists():
            try:
                with open(links_path, "r", encoding="utf-8") as f:
                    links = [TraceLink.model_validate(i) for i in json.load(f)]
            except Exception:
                pass
        elif reqs and tests:
            from reqtrace.engine.linker import TraceLinker
            linker = TraceLinker()
            links = linker.link(reqs, tests)

        review_store = ReviewStore(self.workspace_root / manifest.reviews_file)
        req_map = {r.id: r for r in reqs}
        links = review_store.apply_overlay(links, req_map)

        return reqs, tests, links, review_store

    def export(
        self,
        request: ExportRequest,
        output_dir: Optional[Path | str] = None,
        requirements: Optional[List[Requirement]] = None,
        tests: Optional[List[TestArtifact]] = None,
        links: Optional[List[TraceLink]] = None,
    ) -> ExportResult:
        """
        Executes unified deliverable export based on the specified ExportRequest.
        """
        if output_dir:
            out_dir = Path(output_dir).resolve()
        else:
            out_dir = (self.workspace_root / "exports").resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        # Load data if not supplied
        if requirements is None or tests is None or links is None:
            loaded_reqs, loaded_tests, loaded_links, review_store = self._load_data()
            requirements = requirements if requirements is not None else loaded_reqs
            tests = tests if tests is not None else loaded_tests
            links = links if links is not None else loaded_links
        else:
            manifest = self._get_workspace_manifest()
            review_store = ReviewStore(self.workspace_root / manifest.reviews_file)

        project_meta = self._get_project_metadata()
        tag = request.baseline_tag or project_meta.baseline_id or "CURRENT"
        export_id = f"exp-{uuid.uuid4().hex[:8]}"

        filename: str
        target_path: Path

        if request.format == ExportFormat.CSV:
            filename = f"trace_matrix_{tag}.csv"
            target_path = out_dir / filename
            self.csv_exporter.export(requirements, links, target_path)

        elif request.format == ExportFormat.REQIF:
            filename = f"traced_spec_{tag}.reqif"
            target_path = out_dir / filename
            self.reqif_exporter.export(requirements, links, target_path)

        elif request.format == ExportFormat.HTML:
            filename = f"rtm_report_{tag}.html"
            target_path = out_dir / filename
            # Compute gap analysis result via GapAuditor
            from reqtrace.analysis.gap_auditor import GapAuditor
            auditor = GapAuditor()
            gap_res = auditor.analyze(requirements, tests, links)
            self.html_exporter.generate(
                requirements=requirements,
                tests=tests,
                links=links,
                gap_result=gap_res,
                project_name=project_meta.project_name,
                standard=project_meta.target_standard or "DO-178C",
                output_file=target_path,
            )

        elif request.format == ExportFormat.JSON:
            filename = f"audit_summary_{tag}.json"
            target_path = out_dir / filename
            waivers = review_store.get_requirement_waivers()
            status_report = evaluate_workspace_status(requirements, tests, links, waivers)

            summary_payload = {
                "export_id": export_id,
                "project": project_meta.model_dump(),
                "summary": status_report.model_dump(),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(summary_payload, f, indent=2)
        else:
            raise ValueError(f"Unsupported export format: {request.format}")

        size_bytes = target_path.stat().st_size
        sha256_hash = self._compute_sha256(target_path)

        return ExportResult(
            export_id=export_id,
            format=request.format,
            filename=filename,
            file_path=str(target_path),
            size_bytes=size_bytes,
            sha256=sha256_hash,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
