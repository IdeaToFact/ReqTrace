# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit Tests for AnalysisCoordinator (Granular dirty flags & decoupled review recomputation).
"""

import json
from pathlib import Path
import pytest

from reqtrace.analysis.coordinator import AnalysisCoordinator
from reqtrace.models.requirement import Requirement, RequirementLevel, RequirementType, VerificationMethod
from reqtrace.models.test_artifact import TestArtifact, TestExecutionStatus
from reqtrace.models.trace_link import LinkConfidence, ReviewEvent, ReviewStatus, TraceLink, VerificationStatus
from reqtrace.workspace.manager import WorkspaceManager


@pytest.fixture
def coordinator_workspace(tmp_path: Path):
    ws_dir = tmp_path / "coordinator_ws"
    ws_dir.mkdir()
    manager = WorkspaceManager(global_registry_path=tmp_path / "reg.json")
    manager.init_workspace(ws_dir, project_name="Coordinator Test Proj")

    reqs = [
        Requirement(
            id="REQ-NAV-001",
            title="GPS Acquisition Latency",
            description="The system shall acquire GPS lock within 2.0 seconds.",
            level=RequirementLevel.HIGH_LEVEL,
            is_normative=True,
            verification_method=VerificationMethod.TEST,
            source_file="spec.reqif",
        ),
        Requirement(
            id="REQ-NAV-002",
            title="Dead Reckoning Mode",
            description="The system shall fallback to inertial dead reckoning upon GPS signal loss.",
            level=RequirementLevel.HIGH_LEVEL,
            is_normative=True,
            verification_method=VerificationMethod.TEST,
            source_file="spec.reqif",
        ),
    ]
    with open(ws_dir / "requirements.json", "w", encoding="utf-8") as f:
        json.dump([r.model_dump() for r in reqs], f)

    tests = [
        TestArtifact(
            id="tests/test_nav.py::test_gps_lock_time",
            file_path="tests/test_nav.py",
            line_start=15,
            line_end=25,
            framework="pytest",
            assertion_statements=["assert lock_time <= 2.0"],
            execution_status=TestExecutionStatus.PASSED,
        ),
        TestArtifact(
            id="tests/test_nav.py::test_dead_reckoning",
            file_path="tests/test_nav.py",
            line_start=30,
            line_end=45,
            framework="pytest",
            assertion_statements=["assert mode == 'dead_reckoning'"],
            execution_status=TestExecutionStatus.PASSED,
        ),
    ]
    with open(ws_dir / "tests.json", "w", encoding="utf-8") as f:
        json.dump([t.model_dump() for t in tests], f)

    links = [
        TraceLink(
            req_id="REQ-NAV-001",
            test_id="tests/test_nav.py::test_gps_lock_time",
            confidence=LinkConfidence.EXPLICIT_TAG,
            confidence_score=1.0,
            evidence_span="assert lock_time <= 2.0",
            file_offset=(150, 200),
            justification="Explicit @traced tag",
            is_verified=True,
        ),
        TraceLink(
            req_id="REQ-NAV-002",
            test_id="tests/test_nav.py::test_dead_reckoning",
            confidence=LinkConfidence.HIGH,
            confidence_score=0.88,
            evidence_span="assert mode == 'dead_reckoning'",
            file_offset=(250, 300),
            justification="Fuzzy semantic match",
            is_verified=True,
            is_candidate=True,  # Fuzzy link awaiting human confirmation
            match_strategy="rapidfuzz",
            match_reason="Token set ratio 88%",
        ),
    ]
    with open(ws_dir / "links.json", "w", encoding="utf-8") as f:
        json.dump([l.model_dump() for l in links], f)

    return ws_dir, manager


def test_coordinator_initial_load_and_performance_invariant(coordinator_workspace) -> None:
    ws_dir, manager = coordinator_workspace
    coord = AnalysisCoordinator(ws_dir, workspace_manager=manager)

    # Initial status computation
    report1 = coord.get_status()
    assert report1.total_normative == 2
    assert report1.verified_count == 0  # Neither has formal human review yet
    assert report1.linked_passing_count == 1  # REQ-NAV-001 is linked_passing
    assert report1.unverified_gaps == 1  # REQ-NAV-002 is candidate (gap)

    initial_relinks = coord.relink_count
    initial_recomputes = coord.status_recompute_count
    assert initial_relinks == 1
    assert initial_recomputes == 1

    # ARCHITECTURAL PERFORMANCE INVARIANT CHECK:
    # A review submission shall NEVER invoke requirement-to-test relinking.
    # We approve the candidate link for REQ-NAV-002:
    report2 = coord.record_candidate_action(
        action="approve",
        req_id="REQ-NAV-002",
        test_id="tests/test_nav.py::test_dead_reckoning",
        comment="Confirmed by DER Alice",
        reviewer="Alice <alice@aero.org>",
    )

    # Verify zero additional relink calls were made!
    assert coord.relink_count == initial_relinks, "Violation: relinker was invoked on review submission!"
    assert coord.status_recompute_count == initial_recomputes + 1

    # Verify updated verification status
    assert report2.verified_count == 1  # REQ-NAV-002 now verified!
    assert report2.unverified_gaps == 0  # Zero gaps remaining!


def test_coordinator_dirty_flag_invalidation(coordinator_workspace) -> None:
    ws_dir, manager = coordinator_workspace
    coord = AnalysisCoordinator(ws_dir, workspace_manager=manager)

    coord.get_status()
    relinks_before = coord.relink_count

    # Simulate requirement specification change
    coord.invalidate_requirements()
    assert coord.reqs_dirty is True

    # Next status call MUST trigger relink pass
    coord.get_status()
    assert coord.relink_count == relinks_before + 1
    assert coord.reqs_dirty is False


def test_coordinator_candidate_rejection(coordinator_workspace) -> None:
    ws_dir, manager = coordinator_workspace
    coord = AnalysisCoordinator(ws_dir, workspace_manager=manager)

    # Reject candidate link
    report = coord.record_candidate_action(
        action="reject",
        req_id="REQ-NAV-002",
        test_id="tests/test_nav.py::test_dead_reckoning",
        comment="Fuzzy match rejected - test does not assert fallback timeout.",
    )

    # Link rejected means REQ-NAV-002 remains unverified gap with ALL_LINKS_REJECTED reason
    assert report.unverified_gaps == 1
    from reqtrace.analysis.status import UnverifiedReasonCode
    assert report.gap_reasons[UnverifiedReasonCode.ALL_LINKS_REJECTED] == 1
