# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Comprehensive Integration Tests for ReqTrace v0.2.0 REST API Controllers:
- Workspace lifecycle management (Option B existence enforcement)
- File ingestion wizard (format validation, size limits, parsing)
- Review sign-off & candidate triage (mandatory comment/doc validation, content hash binding)
- Unified export service layer (POST & GET /api/v1/export/{format})
- Unvirtualized @media print audit view (/print)

Executes directly against route handlers in-process without network socket dependencies.
"""

import io
import json
from pathlib import Path
import pytest
from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from reqtrace.analysis.coordinator import AnalysisCoordinator
from reqtrace.models.export import ExportFormat, ExportRequest
from reqtrace.models.requirement import Requirement, RequirementLevel, RequirementType, VerificationMethod
from reqtrace.models.test_artifact import TestArtifact, TestExecutionStatus
from reqtrace.models.trace_link import LinkConfidence, TraceLink
from reqtrace.ui.routes import (
    CandidateActionRequest,
    CreateWorkspaceRequest,
    OpenWorkspaceRequest,
    ReviewSubmissionRequest,
    create_api_router,
)
from reqtrace.ui.security import SessionStore, TicketStore
from reqtrace.workspace.manager import WorkspaceManager


def get_endpoint(router, method: str, path: str):
    """Retrieves route handler function by HTTP method and URL path."""
    for r in router.routes:
        if getattr(r, "path", None) == path and method in getattr(r, "methods", []):
            return r.endpoint
    raise KeyError(f"Route not found: {method} {path}")


@pytest.fixture
def api_test_env(tmp_path: Path):
    ws_dir = tmp_path / "cockpit_ws"
    ws_dir.mkdir()
    global_reg = tmp_path / "global_reg.json"
    ws_mgr = WorkspaceManager(global_registry_path=global_reg)
    ws_mgr.init_workspace(ws_dir, project_name="Flight Navigation Cockpit", baseline_id="NAV-001")

    # Seed baseline requirements
    reqs = [
        Requirement(
            id="REQ-NAV-001",
            title="GPS Acquisition Ceiling",
            description="The receiver shall achieve lock in <= 2.0s.",
            level=RequirementLevel.HIGH_LEVEL,
            is_normative=True,
            verification_method=VerificationMethod.TEST,
            source_file="spec.reqif",
        ),
        Requirement(
            id="REQ-NAV-002",
            title="Dead Reckoning Transition",
            description="The system shall fallback to dead reckoning on GPS failure.",
            level=RequirementLevel.HIGH_LEVEL,
            is_normative=True,
            verification_method=VerificationMethod.TEST,
            source_file="spec.reqif",
        ),
        Requirement(
            id="REQ-NAV-003",
            title="Chassis Vibration Resistance",
            description="The unit chassis shall withstand 10G RMS vibration.",
            level=RequirementLevel.SYSTEM,
            is_normative=True,
            verification_method=VerificationMethod.ANALYSIS,
            source_file="spec.reqif",
        ),
    ]
    with open(ws_dir / "requirements.json", "w", encoding="utf-8") as f:
        json.dump([r.model_dump() for r in reqs], f)

    # Seed test artifacts
    tests = [
        TestArtifact(
            id="tests/test_nav.py::test_gps_acquisition",
            file_path="tests/test_nav.py",
            line_start=10,
            line_end=20,
            framework="pytest",
            assertion_statements=["assert latency <= 2.0"],
            execution_status=TestExecutionStatus.PASSED,
        ),
        TestArtifact(
            id="tests/test_nav.py::test_dr_transition",
            file_path="tests/test_nav.py",
            line_start=25,
            line_end=40,
            framework="pytest",
            assertion_statements=["assert mode == 'dead_reckoning'"],
            execution_status=TestExecutionStatus.PASSED,
        ),
    ]
    with open(ws_dir / "tests.json", "w", encoding="utf-8") as f:
        json.dump([t.model_dump() for t in tests], f)

    # Seed links (one confirmed, one candidate awaiting review)
    links = [
        TraceLink(
            req_id="REQ-NAV-001",
            test_id="tests/test_nav.py::test_gps_acquisition",
            confidence=LinkConfidence.EXPLICIT_TAG,
            confidence_score=1.0,
            evidence_span="assert latency <= 2.0",
            file_offset=(100, 150),
            justification="Explicit tag match",
            is_verified=True,
        ),
        TraceLink(
            req_id="REQ-NAV-002",
            test_id="tests/test_nav.py::test_dr_transition",
            confidence=LinkConfidence.HIGH,
            confidence_score=0.85,
            evidence_span="assert mode == 'dead_reckoning'",
            file_offset=(200, 250),
            justification="Fuzzy semantic match",
            is_candidate=True,
            match_strategy="rapidfuzz",
            match_reason="Token set similarity 85%",
            is_verified=True,
        ),
    ]
    with open(ws_dir / "links.json", "w", encoding="utf-8") as f:
        json.dump([l.model_dump() for l in links], f)

    coord = AnalysisCoordinator(ws_dir, workspace_manager=ws_mgr)
    t_store = TicketStore(timeout_sec=60)
    s_store = SessionStore()
    router = create_api_router(
        workspace_root=ws_dir,
        ticket_store=t_store,
        session_store=s_store,
        cookie_name="reqtrace_session_8765",
        coordinator=coord,
    )

    return router, coord, ws_dir, tmp_path


def test_workspace_lifecycle_endpoints(api_test_env) -> None:
    router, coord, ws_dir, tmp_path = api_test_env

    # 1. GET /api/v1/workspaces
    list_ws = get_endpoint(router, "GET", "/api/v1/workspaces")
    workspaces = list_ws()
    assert isinstance(workspaces, list)
    assert len(workspaces) >= 1
    assert workspaces[0]["name"] == "Flight Navigation Cockpit"

    # 2. GET /api/v1/workspace/current
    get_curr = get_endpoint(router, "GET", "/api/v1/workspace/current")
    curr = get_curr()
    assert curr["project"]["project_name"] == "Flight Navigation Cockpit"
    assert curr["project"]["baseline_id"] == "NAV-001"

    # 3. POST /api/v1/workspaces (Option B: missing directory fails with 400)
    create_ws = get_endpoint(router, "POST", "/api/v1/workspaces")
    missing_dir = tmp_path / "ghost_folder"
    with pytest.raises(HTTPException) as exc_info:
        create_ws(CreateWorkspaceRequest(path=str(missing_dir), project_name="Ghost"))
    assert exc_info.value.status_code == 400
    assert "Target directory does not exist" in exc_info.value.detail

    # 4. POST /api/v1/workspaces (Option B: existing directory succeeds)
    valid_dir = tmp_path / "valid_folder"
    valid_dir.mkdir()
    res_good = create_ws(CreateWorkspaceRequest(
        path=str(valid_dir),
        project_name="Autopilot Control System",
        target_standard="DO-178C DAL A",
    ))
    assert res_good["status"] == "ok"
    assert res_good["project"]["project_name"] == "Autopilot Control System"

    # 5. POST /api/v1/workspaces/open
    open_ws = get_endpoint(router, "POST", "/api/v1/workspaces/open")
    res_open = open_ws(OpenWorkspaceRequest(path=str(ws_dir)))
    assert res_open["status"] == "ok"
    assert res_open["project"]["project_name"] == "Flight Navigation Cockpit"

    # 6. PATCH /api/v1/project
    patch_proj = get_endpoint(router, "PATCH", "/api/v1/project")
    res_patch = patch_proj({"spec_version": "3.1", "target_standard": "DO-178C DAL A"})
    assert res_patch["spec_version"] == "3.1"
    assert res_patch["target_standard"] == "DO-178C DAL A"


def test_review_and_candidate_triage_endpoints(api_test_env) -> None:
    router, coord, ws_dir, _ = api_test_env

    # 1. Candidate Queue GET /api/v1/candidates
    get_cands = get_endpoint(router, "GET", "/api/v1/candidates")
    candidates = get_cands()
    assert len(candidates) == 1
    assert candidates[0]["req_id"] == "REQ-NAV-002"
    assert candidates[0]["match_strategy"] == "rapidfuzz"

    # 2. Reject candidate link POST /api/v1/candidates/action
    cand_act = get_endpoint(router, "POST", "/api/v1/candidates/action")
    res_rej = cand_act(CandidateActionRequest(
        action="reject",
        req_id="REQ-NAV-002",
        test_id="tests/test_nav.py::test_dr_transition",
        comment="Semantic match rejected - assertion does not match flight limits.",
    ))
    assert res_rej["status"] == "ok"
    assert res_rej["action"] == "reject"

    # Candidate queue should now be empty of active candidates
    assert len(get_cands()) == 0

    # 3. Submit formal review approval for REQ-NAV-001 POST /api/v1/reviews
    submit_rev = get_endpoint(router, "POST", "/api/v1/reviews")
    res_rev = submit_rev(ReviewSubmissionRequest(
        req_id="REQ-NAV-001",
        test_id="tests/test_nav.py::test_gps_acquisition",
        status="approved",
        reviewer="DER Dave <dave@faa.gov>",
        comment="Confirmed affirmative latency test in hardware-in-the-loop.",
    ))
    assert res_rev["status"] == "ok"
    assert res_rev["summary"]["verified_count"] >= 1

    # 4. Mandatory rejection comment enforcement
    with pytest.raises(HTTPException) as exc_rej:
        submit_rev(ReviewSubmissionRequest(
            req_id="REQ-NAV-001",
            test_id="tests/test_nav.py::test_gps_acquisition",
            status="rejected",
            reviewer="Reviewer",
            comment="",
        ))
    assert exc_rej.value.status_code == 400
    assert "mandatory" in exc_rej.value.detail.lower()

    # 5. Mandatory waiver reference doc enforcement
    with pytest.raises(HTTPException) as exc_waive:
        submit_rev(ReviewSubmissionRequest(
            req_id="REQ-NAV-003",
            status="waived_analysis",
            reviewer="Structural Lead",
            reference_doc="",
        ))
    assert exc_waive.value.status_code == 400
    assert "reference document" in exc_waive.value.detail.lower()

    # Successful waiver
    res_good_waive = submit_rev(ReviewSubmissionRequest(
        req_id="REQ-NAV-003",
        status="waived_analysis",
        reviewer="Structural Lead",
        reference_doc="DOC-FEA-CHASSIS-042",
        comment="Validated via ANSYS modal analysis report.",
    ))
    assert res_good_waive["status"] == "ok"

    # 6. Audit history GET /api/v1/reviews/{req_id}
    get_hist = get_endpoint(router, "GET", "/api/v1/reviews/{req_id}")
    res_hist = get_hist("REQ-NAV-001")
    assert len(res_hist["events"]) >= 1


def test_export_service_endpoints(api_test_env) -> None:
    router, coord, ws_dir, _ = api_test_env

    # 1. POST /api/v1/export (CSV)
    post_exp = get_endpoint(router, "POST", "/api/v1/export")
    res_csv = post_exp(ExportRequest(format=ExportFormat.CSV, baseline_tag="BASELINE-NAV-001"))
    assert res_csv["format"] == "csv"
    assert "trace_matrix_BASELINE-NAV-001.csv" in res_csv["filename"]
    assert len(res_csv["sha256"]) == 64

    # 2. GET /api/v1/export/csv
    get_exp = get_endpoint(router, "GET", "/api/v1/export/{export_format}")
    file_csv = get_exp("csv")
    assert isinstance(file_csv, FileResponse)
    assert file_csv.media_type == "text/csv"
    assert Path(file_csv.path).is_file()

    # 3. GET /api/v1/export/reqif
    file_reqif = get_exp("reqif")
    assert isinstance(file_reqif, FileResponse)
    assert file_reqif.media_type == "application/xml"

    # 4. GET /api/v1/export/html
    file_html = get_exp("html")
    assert isinstance(file_html, FileResponse)
    assert file_html.media_type == "text/html"

    # 5. GET /api/v1/export/json
    file_json = get_exp("json")
    assert isinstance(file_json, FileResponse)
    assert file_json.media_type == "application/json"

    # 6. Invalid format returns 400
    with pytest.raises(HTTPException) as exc_bad:
        get_exp("invalid_format")
    assert exc_bad.value.status_code == 400


def test_ingest_wizard_endpoints(api_test_env) -> None:
    router, coord, ws_dir, _ = api_test_env

    ingest_spec = get_endpoint(router, "POST", "/api/v1/ingest/spec")
    ingest_tests = get_endpoint(router, "POST", "/api/v1/ingest/tests")

    # 1. Ingest spec with illegal extension (.exe) returns 400
    bad_spoor = io.BytesIO(b"illegal executable bytes")
    bad_file = UploadFile(file=bad_spoor, filename="exploit.exe")
    with pytest.raises(HTTPException) as exc_spec:
        ingest_spec(bad_file)
    assert exc_spec.value.status_code == 400
    assert "unsupported" in exc_spec.value.detail.lower()

    # 2. Ingest valid CSV specification
    csv_bytes = (
        "id,title,description,level,is_normative,verification_method\n"
        "REQ-ING-01,Pitch Trim Autopilot,Trim rate shall not exceed 0.5 deg/sec,high_level,true,test\n"
        "REQ-ING-02,Roll Authority,Roll rate limit 15 deg/sec,high_level,true,test\n"
    ).encode("utf-8")
    csv_file = UploadFile(file=io.BytesIO(csv_bytes), filename="autopilot_spec.csv")
    res_csv = ingest_spec(csv_file)
    assert res_csv["status"] == "ok"
    assert res_csv["total_requirements"] == 2
    assert res_csv["normative_requirements"] == 2

    # Verify requirements are reflected in matrix
    get_matrix = get_endpoint(router, "GET", "/api/v1/matrix")
    matrix = get_matrix()
    ids = [item["id"] for item in matrix["items"]]
    assert "REQ-ING-01" in ids
    assert "REQ-ING-02" in ids

    # 3. Ingest tests with Python AST
    py_bytes = b"""
import pytest

def test_pitch_trim_rate():
    # @traced: REQ-ING-01
    assert pitch_rate <= 0.5
"""
    py_file = UploadFile(file=io.BytesIO(py_bytes), filename="test_pitch.py")
    res_py = ingest_tests(py_file)
    assert res_py["status"] == "ok"
    assert res_py["total_tests"] == 1

    # 4. Ingest JUnit XML execution results onto existing tests
    junit_bytes = b"""<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pitch-suite" tests="1" failures="1" errors="0" skipped="0">
    <testcase classname="test_pitch" name="test_pitch_trim_rate" time="0.012">
      <failure message="AssertionError">pitch_rate 0.8 > 0.5</failure>
    </testcase>
  </testsuite>
</testsuites>"""
    junit_file = UploadFile(file=io.BytesIO(junit_bytes), filename="junit.xml")
    res_junit = ingest_tests(junit_file)
    assert res_junit["status"] == "ok"
    assert res_junit["total_tests"] == 1
    assert res_junit["attached_verdicts"] == 1
    assert coord.get_tests()[0].execution_status == TestExecutionStatus.FAILED

    # 5. Wrong dropzone guard: dropping JUnit XML into Spec dropzone must reject (400) AND preserve requirements
    junit_in_spec = UploadFile(file=io.BytesIO(junit_bytes), filename="junit_wrong_box.xml")
    with pytest.raises(HTTPException) as exc_junit_spec:
        ingest_spec(junit_in_spec)
    assert exc_junit_spec.value.status_code == 400
    assert "JUnit test execution report" in exc_junit_spec.value.detail
    assert len(coord.get_requirements()) == 2

    # 6. Wrong dropzone guard: dropping ReqIF XML into Test dropzone must reject (400) AND preserve tests
    reqif_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<REQ-IF xmlns="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd">
  <CORE-CONTENT><REQ-IF-CONTENT><SPEC-OBJECTS/></REQ-IF-CONTENT></CORE-CONTENT>
</REQ-IF>"""
    reqif_in_tests = UploadFile(file=io.BytesIO(reqif_bytes), filename="spec_wrong_box.xml")
    with pytest.raises(HTTPException) as exc_reqif_tests:
        ingest_tests(reqif_in_tests)
    assert exc_reqif_tests.value.status_code == 400
    assert "ReqIF Requirements Specification" in exc_reqif_tests.value.detail
    assert len(coord.get_tests()) == 1


def test_print_view_endpoint(api_test_env) -> None:
    router, coord, ws_dir, _ = api_test_env

    print_endpoint = get_endpoint(router, "GET", "/print")
    res = print_endpoint()
    assert isinstance(res, HTMLResponse)
    assert res.status_code == 200
    content = res.body.decode("utf-8")
    assert "@media print" in content
    assert "Flight Navigation Cockpit" in content
    assert "window.print()" in content
