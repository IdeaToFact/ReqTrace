# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for TraceLinker and Live Verification.
"""

from reqtrace.engine.linker import TraceLinker
from reqtrace.models.requirement import Requirement
from reqtrace.models.test_artifact import TestArtifact, TestExecutionStatus
from reqtrace.models.trace_link import LinkConfidence


def test_tag_and_live_verification_link() -> None:
    req = Requirement(
        id="REQ-NAV-0104",
        title="GPS Loss Failsafe",
        description="Switch to dead-reckoning within 200ms",
        source_file="spec.reqif",
    )

    # Test 1: Passed in CI
    t1 = TestArtifact(
        id="test_nav.py::test_gps_loss_switches_to_dead_reckoning",
        file_path="tests/test_nav.py",
        line_start=10,
        line_end=20,
        framework="pytest",
        declared_req_refs=["REQ-NAV-0104"],
        assertion_statements=["assert nav.mode == 'INERTIAL'"],
        execution_status=TestExecutionStatus.PASSED,
    )

    linker = TraceLinker()
    links = linker.link([req], [t1])

    assert len(links) == 1
    assert links[0].req_id == "REQ-NAV-0104"
    assert links[0].test_id == t1.id
    assert links[0].confidence == LinkConfidence.VERIFIED
    assert links[0].confidence_score == 1.0
    assert links[0].is_verified is True  # Passed test = Live Verified!


def test_failed_test_yields_unverified_link() -> None:
    req = Requirement(
        id="REQ-PWR-001",
        title="Battery Voltage",
        description="Battery must stay above 24V",
        source_file="spec.reqif",
    )

    # Test failed in CI!
    t_failed = TestArtifact(
        id="test_pwr.py::test_battery_voltage",
        file_path="tests/test_pwr.py",
        line_start=1,
        line_end=10,
        framework="pytest",
        declared_req_refs=["REQ-PWR-001"],
        assertion_statements=["assert voltage >= 24.0"],
        execution_status=TestExecutionStatus.FAILED,  # Failed!
    )

    linker = TraceLinker()
    links = linker.link([req], [t_failed])

    assert len(links) == 1
    assert links[0].is_verified is False  # A failed test = unlinked/unverified requirement!

