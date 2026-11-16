# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for HTMLReportGenerator.
"""

from pathlib import Path
from reqtrace.models.requirement import Requirement
from reqtrace.models.rtm import GapAnalysisResult
from reqtrace.models.test_artifact import TestArtifact, TestExecutionStatus
from reqtrace.models.trace_link import LinkConfidence, TraceLink
from reqtrace.reports.html_report import HTMLReportGenerator


def test_html_report_generation(tmp_path: Path) -> None:
    req = Requirement(id="REQ-01", title="Req 1", description="Description 1", source_file="spec.reqif")
    test = TestArtifact(id="t1.py::test_case", file_path="t1.py", line_start=1, line_end=5, framework="pytest", execution_status=TestExecutionStatus.PASSED)
    link = TraceLink(
        req_id="REQ-01",
        test_id="t1.py::test_case",
        confidence=LinkConfidence.VERIFIED,
        confidence_score=1.0,
        evidence_span="assert True",
        file_offset=(1, 5),
        justification="Verified",
        is_verified=True,
    )
    gap = GapAnalysisResult(
        total_requirements=1,
        normative_requirements=1,
        covered_requirements=1,
        orphan_requirements=[],
        total_tests=1,
        unlinked_tests=[],
        failed_tests=[],
        stale_links=[],
        coverage_percentage=100.0,
        is_passing=True,
    )

    out_file = tmp_path / "report.html"
    gen = HTMLReportGenerator()
    result = gen.generate([req], [test], [link], gap, output_file=out_file)

    assert result.exists()
    content = result.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "ReqTrace RTM Dashboard" in content
    assert "REQ-01" in content
    assert "t1.py::test_case" in content
    assert "LIVE VERIFIED" in content
    assert "100.0%" in content

