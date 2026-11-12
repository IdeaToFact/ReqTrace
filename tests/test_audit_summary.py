# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for audit-summary command and CLI manager dashboard.
"""

import json
from pathlib import Path
from typer.testing import CliRunner
from reqtrace.cli import app
from reqtrace.models.requirement import Requirement
from reqtrace.models.test_artifact import TestArtifact, TestExecutionStatus

runner = CliRunner()


def test_cli_audit_summary(tmp_path: Path) -> None:
    req = Requirement(id="REQ-01", title="Req 1", description="Description 1", source_file="spec.reqif")
    test = TestArtifact(
        id="t1.py::test_case",
        file_path="t1.py",
        line_start=1,
        line_end=5,
        framework="pytest",
        declared_req_refs=["REQ-01"],
        assertion_statements=["assert True"],
        execution_status=TestExecutionStatus.PASSED,
    )

    reqs_path = tmp_path / "reqs.json"
    tests_path = tmp_path / "tests.json"

    reqs_path.write_text(json.dumps([req.model_dump()]), encoding="utf-8")
    tests_path.write_text(json.dumps([test.model_dump()]), encoding="utf-8")

    result = runner.invoke(app, ["audit-summary", "--reqs", str(reqs_path), "--tests", str(tests_path)])
    assert result.exit_code == 0
    assert "ReqTrace Executive Audit Summary" in result.output
    assert "Live Verified:" in result.output
    assert "Coverage:" in result.output
    assert "PASS (Audit Ready)" in result.output

