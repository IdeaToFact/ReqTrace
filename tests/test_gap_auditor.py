# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for GapAuditor and CI Gating.
"""

from reqtrace.analysis.gap_auditor import GapAuditor
from reqtrace.config import ThresholdsConfig
from reqtrace.models.requirement import Requirement
from reqtrace.models.test_artifact import TestArtifact, TestExecutionStatus
from reqtrace.models.trace_link import LinkConfidence, TraceLink


def test_gap_auditor_detects_orphans_and_unlinked_tests() -> None:
    req1 = Requirement(id="REQ-01", title="Req 1", description="Normative req 1", source_file="spec.reqif")
    req2 = Requirement(id="REQ-02", title="Req 2", description="Normative req 2", source_file="spec.reqif")  # Orphan!
    req_info = Requirement(id="INFO-01", title="Info", description="Header", is_normative=False, source_file="spec.reqif")

    t1 = TestArtifact(id="test_01", file_path="t.py", line_start=1, line_end=5, framework="pytest", execution_status=TestExecutionStatus.PASSED)
    t_rogue = TestArtifact(id="test_rogue", file_path="t.py", line_start=10, line_end=15, framework="pytest", execution_status=TestExecutionStatus.PASSED)

    link1 = TraceLink(
        req_id="REQ-01",
        test_id="test_01",
        confidence=LinkConfidence.VERIFIED,
        confidence_score=1.0,
        evidence_span="assert True",
        file_offset=(1, 5),
        justification="Verified",
        is_verified=True,
    )

    thresholds = ThresholdsConfig(
        min_coverage_pct=50.0,
        fail_on_orphans=False,
        fail_on_test_failures=True,
        fail_on_stale_reviews=True,
    )
    auditor = GapAuditor(thresholds)
    result = auditor.analyze([req1, req2, req_info], [t1, t_rogue], [link1])

    assert result.total_requirements == 3
    assert result.normative_requirements == 2
    assert result.covered_requirements == 1
    assert result.orphan_requirements == ["REQ-02"]
    assert result.unlinked_tests == ["test_rogue"]
    assert result.coverage_percentage == 50.0
    assert result.is_passing is True  # Meets 50% min coverage


def test_gap_auditor_ci_gate_fails_on_orphans() -> None:
    req1 = Requirement(id="REQ-01", title="Req 1", description="Req 1", source_file="spec.reqif")
    req2 = Requirement(id="REQ-02", title="Req 2", description="Req 2", source_file="spec.reqif")

    t1 = TestArtifact(id="test_01", file_path="t.py", line_start=1, line_end=5, framework="pytest", execution_status=TestExecutionStatus.PASSED)
    link1 = TraceLink(
        req_id="REQ-01",
        test_id="test_01",
        confidence=LinkConfidence.VERIFIED,
        confidence_score=1.0,
        evidence_span="assert True",
        file_offset=(1, 5),
        justification="Verified",
        is_verified=True,
    )

    thresholds = ThresholdsConfig(
        min_coverage_pct=100.0,
        fail_on_orphans=True,  # Strict CI rule!
    )
    auditor = GapAuditor(thresholds)
    result = auditor.analyze([req1, req2], [t1], [link1])

    assert result.is_passing is False
    assert any("orphan requirements" in err.lower() for err in result.gating_errors)

