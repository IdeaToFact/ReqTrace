# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit Tests for ExportManager (unified exports: CSV, ReqIF, HTML, JSON).
"""

import json
from pathlib import Path
import pytest

from reqtrace.models.export import ExportFormat, ExportRequest, ExportResult
from reqtrace.models.requirement import Requirement, RequirementLevel, RequirementType, VerificationMethod
from reqtrace.models.test_artifact import TestArtifact, TestExecutionStatus
from reqtrace.models.trace_link import LinkConfidence, ReviewStatus, TraceLink
from reqtrace.reports.exporter import ExportManager
from reqtrace.workspace.manager import WorkspaceManager


@pytest.fixture
def sample_workspace(tmp_path: Path):
    ws_dir = tmp_path / "export_ws"
    ws_dir.mkdir()
    manager = WorkspaceManager(global_registry_path=tmp_path / "reg.json")
    manager.init_workspace(ws_dir, project_name="Export Test Proj", baseline_id="BASE-100")

    reqs = [
        Requirement(
            id="REQ-TEST-001",
            title="Engine Temperature Ceiling",
            description="The temperature shall not exceed 105C.",
            level=RequirementLevel.HIGH_LEVEL,
            is_normative=True,
            verification_method=VerificationMethod.TEST,
            source_file="spec.reqif",
        )
    ]
    with open(ws_dir / "requirements.json", "w", encoding="utf-8") as f:
        json.dump([r.model_dump() for r in reqs], f)

    tests = [
        TestArtifact(
            id="tests/test_engine.py::test_temp_limit",
            file_path="tests/test_engine.py",
            line_start=10,
            line_end=20,
            framework="pytest",
            assertion_statements=["assert temp <= 105"],
            execution_status=TestExecutionStatus.PASSED,
        )
    ]
    with open(ws_dir / "tests.json", "w", encoding="utf-8") as f:
        json.dump([t.model_dump() for t in tests], f)

    links = [
        TraceLink(
            req_id="REQ-TEST-001",
            test_id="tests/test_engine.py::test_temp_limit",
            confidence=LinkConfidence.EXPLICIT_TAG,
            confidence_score=1.0,
            evidence_span="assert temp <= 105",
            file_offset=(100, 150),
            justification="Explicit @traced tag",
            is_verified=True,
            review_status=ReviewStatus.APPROVED,
        )
    ]
    with open(ws_dir / "links.json", "w", encoding="utf-8") as f:
        json.dump([l.model_dump() for l in links], f)

    return ws_dir


def test_export_manager_csv(sample_workspace: Path) -> None:
    exporter = ExportManager(sample_workspace)
    req = ExportRequest(format=ExportFormat.CSV, baseline_tag="BASE-100")
    result = exporter.export(req)

    assert isinstance(result, ExportResult)
    assert result.format == ExportFormat.CSV
    assert result.filename == "trace_matrix_BASE-100.csv"
    assert Path(result.file_path).is_file()
    assert result.size_bytes > 0
    assert len(result.sha256) == 64

    # Verify CSV contents
    content = Path(result.file_path).read_text(encoding="utf-8")
    assert "REQ-TEST-001" in content
    assert "Engine Temperature Ceiling" in content


def test_export_manager_reqif(sample_workspace: Path) -> None:
    exporter = ExportManager(sample_workspace)
    req = ExportRequest(format=ExportFormat.REQIF, baseline_tag="BASE-100")
    result = exporter.export(req)

    assert result.format == ExportFormat.REQIF
    assert result.filename == "traced_spec_BASE-100.reqif"
    assert Path(result.file_path).is_file()

    content = Path(result.file_path).read_text(encoding="utf-8")
    assert "REQ-TEST-001" in content
    assert "SPEC-RELATION" in content


def test_export_manager_html(sample_workspace: Path) -> None:
    exporter = ExportManager(sample_workspace)
    req = ExportRequest(format=ExportFormat.HTML, baseline_tag="BASE-100")
    result = exporter.export(req)

    assert result.format == ExportFormat.HTML
    assert result.filename == "rtm_report_BASE-100.html"
    assert Path(result.file_path).is_file()

    content = Path(result.file_path).read_text(encoding="utf-8")
    assert "REQ-TEST-001" in content
    assert "Export Test Proj" in content


def test_export_manager_json(sample_workspace: Path) -> None:
    exporter = ExportManager(sample_workspace)
    req = ExportRequest(format=ExportFormat.JSON, baseline_tag="BASE-100")
    result = exporter.export(req)

    assert result.format == ExportFormat.JSON
    assert result.filename == "audit_summary_BASE-100.json"
    assert Path(result.file_path).is_file()

    with open(result.file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["project"]["project_name"] == "Export Test Proj"
    assert data["summary"]["verified_count"] == 1
