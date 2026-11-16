# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Comprehensive Table-Driven Test Suite for the ReqTrace Canonical Status Model.
Validates 32 distinct scenarios including two-axis evaluation, multi-link conjunctive
All-Must-Pass aggregation, non-TEST waivers, fuzzy candidate isolation, and invariant proofs.
"""

import pytest
from reqtrace.analysis.status import (
    PRECEDENCE_ORDER,
    UnverifiedReasonCode,
    WorkspaceStatusReport,
    evaluate_workspace_status,
)
from reqtrace.models.requirement import Requirement, RequirementLevel, VerificationMethod
from reqtrace.models.test_artifact import TestArtifact, TestVerdict
from reqtrace.models.trace_link import (
    LinkConfidence,
    ReviewEvent,
    ReviewStatus,
    TraceLink,
    VerificationStatus,
)


def _make_req(
    req_id: str,
    method: VerificationMethod = VerificationMethod.TEST,
    is_normative: bool = True,
) -> Requirement:
    return Requirement(
        id=req_id,
        title=f"Title for {req_id}",
        description=f"Description for {req_id}",
        is_normative=is_normative,
        verification_method=method,
        source_file="specs/sys.reqif",
    )


def _make_test(
    test_id: str,
    verdict: TestVerdict = TestVerdict.PASSED,
    assertions: int = 1,
    is_exec_stale: bool = False,
) -> TestArtifact:
    assert_list = [f"assert state_{i} == True" for i in range(assertions)]
    return TestArtifact(
        id=test_id,
        file_path="tests/test_core.py",
        line_start=10,
        line_end=20,
        framework="pytest",
        assertion_statements=assert_list,
        execution_status=verdict,
    )


def _make_link(
    req_id: str,
    test_id: str,
    confidence: LinkConfidence = LinkConfidence.EXPLICIT_TAG,
    review_status: ReviewStatus = ReviewStatus.APPROVED,
    is_stale: bool = False,
    is_exec_stale: bool = False,
) -> TraceLink:
    return TraceLink(
        req_id=req_id,
        test_id=test_id,
        confidence=confidence,
        confidence_score=0.95,
        evidence_span="assert True",
        file_offset=(0, 11),
        justification="Rule link",
        review_status=review_status,
        is_stale=is_stale,
        is_execution_stale=is_exec_stale,
        is_verified=(review_status == ReviewStatus.APPROVED and not is_stale and not is_exec_stale),
    )


# --- Scenario 1 to 5: Single Link & Candidate Isolation ---

def test_scenario_01_single_passing_approved_link_is_verified() -> None:
    req = _make_req("REQ-01")
    test = _make_test("test_01", TestVerdict.PASSED)
    link = _make_link("REQ-01", "test_01", review_status=ReviewStatus.APPROVED)

    report = evaluate_workspace_status([req], [test], [link])
    assert report.verified_count == 1
    assert report.linked_passing_count == 0
    assert report.unverified_gaps == 0
    assert report.requirement_results["REQ-01"].verification_status == VerificationStatus.VERIFIED


def test_scenario_02_single_passing_unreviewed_link_is_linked_passing() -> None:
    req = _make_req("REQ-02")
    test = _make_test("test_02", TestVerdict.PASSED)
    link = _make_link("REQ-02", "test_02", review_status=ReviewStatus.UNREVIEWED)

    report = evaluate_workspace_status([req], [test], [link])
    assert report.verified_count == 0
    assert report.linked_passing_count == 1
    assert report.unverified_gaps == 0
    assert report.requirement_results["REQ-02"].verification_status == VerificationStatus.LINKED_PASSING


def test_scenario_03_zero_links_is_orphan_no_test() -> None:
    req = _make_req("REQ-03")
    report = evaluate_workspace_status([req], [], [])
    assert report.unverified_gaps == 1
    assert report.gap_reasons[UnverifiedReasonCode.ORPHAN_NO_TEST] == 1
    assert report.requirement_results["REQ-03"].primary_reason == UnverifiedReasonCode.ORPHAN_NO_TEST


def test_scenario_04_fuzzy_candidate_link_earns_zero_coverage() -> None:
    req = _make_req("REQ-04")
    test = _make_test("test_04", TestVerdict.PASSED)
    # High fuzzy match, but unreviewed -> candidate only!
    link = _make_link("REQ-04", "test_04", confidence=LinkConfidence.HIGH, review_status=ReviewStatus.UNREVIEWED)

    report = evaluate_workspace_status([req], [test], [link])
    assert report.verified_count == 0
    assert report.linked_passing_count == 0
    assert report.unverified_gaps == 1
    assert report.gap_reasons[UnverifiedReasonCode.CANDIDATES_PENDING_REVIEW] == 1
    assert report.requirement_results["REQ-04"].candidate_links_count == 1
    assert report.requirement_results["REQ-04"].active_links_count == 0


def test_scenario_05_approved_fuzzy_candidate_promotes_to_active_verified() -> None:
    req = _make_req("REQ-05")
    test = _make_test("test_05", TestVerdict.PASSED)
    # Human approved the fuzzy match!
    link = _make_link("REQ-05", "test_05", confidence=LinkConfidence.HIGH, review_status=ReviewStatus.APPROVED)

    report = evaluate_workspace_status([req], [test], [link])
    assert report.verified_count == 1
    assert report.unverified_gaps == 0
    assert report.requirement_results["REQ-05"].verification_status == VerificationStatus.VERIFIED


# --- Scenario 6 to 8: Rejected Links Handling ---

def test_scenario_06_all_links_rejected_yields_all_links_rejected_reason() -> None:
    req = _make_req("REQ-06")
    test = _make_test("test_06", TestVerdict.PASSED)
    link = _make_link("REQ-06", "test_06", review_status=ReviewStatus.REJECTED)

    report = evaluate_workspace_status([req], [test], [link])
    assert report.unverified_gaps == 1
    assert report.gap_reasons[UnverifiedReasonCode.ALL_LINKS_REJECTED] == 1
    assert report.requirement_results["REQ-06"].primary_reason == UnverifiedReasonCode.ALL_LINKS_REJECTED


def test_scenario_07_one_rejected_one_passing_approved_is_verified() -> None:
    req = _make_req("REQ-07")
    t1 = _make_test("test_07a", TestVerdict.PASSED)
    t2 = _make_test("test_07b", TestVerdict.PASSED)
    l1 = _make_link("REQ-07", "test_07a", review_status=ReviewStatus.REJECTED)
    l2 = _make_link("REQ-07", "test_07b", review_status=ReviewStatus.APPROVED)

    report = evaluate_workspace_status([req], [t1, t2], [l1, l2])
    assert report.verified_count == 1
    assert report.unverified_gaps == 0
    assert report.requirement_results["REQ-07"].rejected_links_count == 1
    assert report.requirement_results["REQ-07"].active_links_count == 1


def test_scenario_08_one_rejected_one_passing_unreviewed_is_linked_passing() -> None:
    req = _make_req("REQ-08")
    t1 = _make_test("test_08a", TestVerdict.PASSED)
    t2 = _make_test("test_08b", TestVerdict.PASSED)
    l1 = _make_link("REQ-08", "test_08a", review_status=ReviewStatus.REJECTED)
    l2 = _make_link("REQ-08", "test_08b", review_status=ReviewStatus.UNREVIEWED)

    report = evaluate_workspace_status([req], [t1, t2], [l1, l2])
    assert report.linked_passing_count == 1
    assert report.unverified_gaps == 0


# --- Scenario 9 to 14: Conjunctive All-Must-Pass & Precedence ---

def test_scenario_09_multi_link_one_failing_causes_test_execution_failed() -> None:
    req = _make_req("REQ-09")
    t1 = _make_test("test_09a", TestVerdict.PASSED)
    t2 = _make_test("test_09b", TestVerdict.FAILED)
    l1 = _make_link("REQ-09", "test_09a", review_status=ReviewStatus.APPROVED)
    l2 = _make_link("REQ-09", "test_09b", review_status=ReviewStatus.APPROVED)

    report = evaluate_workspace_status([req], [t1, t2], [l1, l2])
    assert report.unverified_gaps == 1
    assert report.gap_reasons[UnverifiedReasonCode.TEST_EXECUTION_FAILED] == 1


def test_scenario_10_multi_link_one_skipped_causes_test_execution_skipped() -> None:
    req = _make_req("REQ-10")
    t1 = _make_test("test_10a", TestVerdict.PASSED)
    t2 = _make_test("test_10b", TestVerdict.SKIPPED)
    l1 = _make_link("REQ-10", "test_10a", review_status=ReviewStatus.APPROVED)
    l2 = _make_link("REQ-10", "test_10b", review_status=ReviewStatus.APPROVED)

    report = evaluate_workspace_status([req], [t1, t2], [l1, l2])
    assert report.unverified_gaps == 1
    assert report.gap_reasons[UnverifiedReasonCode.TEST_EXECUTION_SKIPPED] == 1


def test_scenario_11_multi_link_one_unexecuted_causes_test_unexecuted() -> None:
    req = _make_req("REQ-11")
    t1 = _make_test("test_11a", TestVerdict.PASSED)
    t2 = _make_test("test_11b", TestVerdict.UNEXECUTED)
    l1 = _make_link("REQ-11", "test_11a", review_status=ReviewStatus.APPROVED)
    l2 = _make_link("REQ-11", "test_11b", review_status=ReviewStatus.APPROVED)

    report = evaluate_workspace_status([req], [t1, t2], [l1, l2])
    assert report.unverified_gaps == 1
    assert report.gap_reasons[UnverifiedReasonCode.TEST_UNEXECUTED] == 1


def test_scenario_12_precedence_failed_beats_skipped() -> None:
    req = _make_req("REQ-12")
    t1 = _make_test("test_12a", TestVerdict.FAILED)
    t2 = _make_test("test_12b", TestVerdict.SKIPPED)
    l1 = _make_link("REQ-12", "test_12a")
    l2 = _make_link("REQ-12", "test_12b")

    report = evaluate_workspace_status([req], [t1, t2], [l1, l2])
    assert report.requirement_results["REQ-12"].primary_reason == UnverifiedReasonCode.TEST_EXECUTION_FAILED
    assert UnverifiedReasonCode.TEST_EXECUTION_SKIPPED in report.requirement_results["REQ-12"].all_reasons


def test_scenario_13_precedence_skipped_beats_unexecuted() -> None:
    req = _make_req("REQ-13")
    t1 = _make_test("test_13a", TestVerdict.SKIPPED)
    t2 = _make_test("test_13b", TestVerdict.UNEXECUTED)
    l1 = _make_link("REQ-13", "test_13a")
    l2 = _make_link("REQ-13", "test_13b")

    report = evaluate_workspace_status([req], [t1, t2], [l1, l2])
    assert report.requirement_results["REQ-13"].primary_reason == UnverifiedReasonCode.TEST_EXECUTION_SKIPPED


def test_scenario_14_precedence_failed_beats_stale_review() -> None:
    req = _make_req("REQ-14")
    t1 = _make_test("test_14a", TestVerdict.FAILED)
    t2 = _make_test("test_14b", TestVerdict.PASSED)
    l1 = _make_link("REQ-14", "test_14a")
    l2 = _make_link("REQ-14", "test_14b", is_stale=True)

    report = evaluate_workspace_status([req], [t1, t2], [l1, l2])
    assert report.requirement_results["REQ-14"].primary_reason == UnverifiedReasonCode.TEST_EXECUTION_FAILED


# --- Scenario 15 to 19: Staleness & Assertions Checks ---

def test_scenario_15_execution_stale_flagged_when_source_newer() -> None:
    req = _make_req("REQ-15")
    t1 = _make_test("test_15", TestVerdict.PASSED)
    l1 = _make_link("REQ-15", "test_15", is_exec_stale=True)

    report = evaluate_workspace_status([req], [t1], [l1])
    assert report.unverified_gaps == 1
    assert report.gap_reasons[UnverifiedReasonCode.EXECUTION_STALE] == 1


def test_scenario_16_review_stale_flagged_when_content_hash_drifted() -> None:
    req = _make_req("REQ-16")
    t1 = _make_test("test_16", TestVerdict.PASSED)
    l1 = _make_link("REQ-16", "test_16", is_stale=True)

    report = evaluate_workspace_status([req], [t1], [l1])
    assert report.unverified_gaps == 1
    assert report.gap_reasons[UnverifiedReasonCode.REVIEW_STALE] == 1


def test_scenario_17_precedence_execution_stale_beats_review_stale() -> None:
    req = _make_req("REQ-17")
    t1 = _make_test("test_17a", TestVerdict.PASSED)
    t2 = _make_test("test_17b", TestVerdict.PASSED)
    l1 = _make_link("REQ-17", "test_17a", is_exec_stale=True)
    l2 = _make_link("REQ-17", "test_17b", is_stale=True)

    report = evaluate_workspace_status([req], [t1, t2], [l1, l2])
    assert report.requirement_results["REQ-17"].primary_reason == UnverifiedReasonCode.EXECUTION_STALE


def test_scenario_18_no_affirmative_assertions_causes_no_assertions_reason() -> None:
    req = _make_req("REQ-18")
    t1 = _make_test("test_18", TestVerdict.PASSED, assertions=0)
    l1 = _make_link("REQ-18", "test_18")

    report = evaluate_workspace_status([req], [t1], [l1])
    assert report.unverified_gaps == 1
    assert report.gap_reasons[UnverifiedReasonCode.NO_ASSERTIONS] == 1


def test_scenario_19_precedence_failed_beats_no_assertions() -> None:
    req = _make_req("REQ-19")
    t1 = _make_test("test_19a", TestVerdict.FAILED, assertions=1)
    t2 = _make_test("test_19b", TestVerdict.PASSED, assertions=0)
    l1 = _make_link("REQ-19", "test_19a")
    l2 = _make_link("REQ-19", "test_19b")

    report = evaluate_workspace_status([req], [t1, t2], [l1, l2])
    assert report.requirement_results["REQ-19"].primary_reason == UnverifiedReasonCode.TEST_EXECUTION_FAILED


# --- Scenario 20 to 24: Verification Methods Beyond TEST (Waivers) ---

def test_scenario_20_non_test_analysis_awaiting_verification() -> None:
    req = _make_req("REQ-20", method=VerificationMethod.ANALYSIS)
    report = evaluate_workspace_status([req], [], [])
    assert report.unverified_gaps == 1
    assert report.gap_reasons[UnverifiedReasonCode.AWAITING_NON_TEST_VERIFICATION] == 1


def test_scenario_21_non_test_analysis_waived_analysis_is_verified() -> None:
    req = _make_req("REQ-21", method=VerificationMethod.ANALYSIS)
    rev = ReviewEvent(
        req_id="REQ-21",
        status=ReviewStatus.WAIVED_ANALYSIS,
        reviewed_by="der_specialist",
        reference_doc="DOC-FEA-WING-SPAR-REV-D",
        comment="FEA stress calculation confirmed margin > 1.5",
    )
    report = evaluate_workspace_status([req], [], [], reviews={"REQ-21": rev})
    assert report.verified_count == 1
    assert report.unverified_gaps == 0
    assert report.requirement_results["REQ-21"].verification_status == VerificationStatus.VERIFIED


def test_scenario_22_non_test_analysis_rejected_review() -> None:
    req = _make_req("REQ-22", method=VerificationMethod.ANALYSIS)
    rev = ReviewEvent(
        req_id="REQ-22",
        status=ReviewStatus.REJECTED,
        reviewed_by="der_specialist",
        comment="Calculation methodology does not meet DO-178C requirements",
    )
    report = evaluate_workspace_status([req], [], [], reviews={"REQ-22": rev})
    assert report.unverified_gaps == 1
    assert report.gap_reasons[UnverifiedReasonCode.ALL_LINKS_REJECTED] == 1


def test_scenario_23_non_test_inspection_waived_is_verified() -> None:
    req = _make_req("REQ-23", method=VerificationMethod.INSPECTION)
    rev = ReviewEvent(
        req_id="REQ-23",
        status=ReviewStatus.WAIVED_ANALYSIS,
        reviewed_by="qa_inspector",
        reference_doc="INSP-REPORT-2026-09",
    )
    report = evaluate_workspace_status([req], [], [], reviews={"REQ-23": rev})
    assert report.verified_count == 1
    assert report.unverified_gaps == 0


def test_scenario_24_non_test_review_awaiting_checklist() -> None:
    req = _make_req("REQ-24", method=VerificationMethod.REVIEW)
    report = evaluate_workspace_status([req], [], [])
    assert report.gap_reasons[UnverifiedReasonCode.AWAITING_NON_TEST_VERIFICATION] == 1


# --- Scenario 25 to 28: Non-Normative Filtering & Mathematical Invariants ---

def test_scenario_25_non_normative_requirements_excluded_from_totals() -> None:
    req_norm = _make_req("REQ-25A", is_normative=True)
    req_info = _make_req("REQ-25B", is_normative=False)
    test = _make_test("test_25", TestVerdict.PASSED)
    link = _make_link("REQ-25A", "test_25", review_status=ReviewStatus.APPROVED)

    report = evaluate_workspace_status([req_norm, req_info], [test], [link])
    assert report.total_requirements == 2
    assert report.total_normative == 1
    assert report.non_normative_count == 1
    assert report.verified_count == 1
    assert report.audit_verified_coverage_pct == 100.0


def test_scenario_26_mixed_workspace_mathematical_invariant_proof() -> None:
    reqs = [
        _make_req("REQ-A1"),  # verified
        _make_req("REQ-A2"),  # linked passing
        _make_req("REQ-A3"),  # failing
        _make_req("REQ-A4"),  # skipped
        _make_req("REQ-A5"),  # unexecuted
        _make_req("REQ-A6"),  # orphan
        _make_req("REQ-A7"),  # candidate only
        _make_req("REQ-A8"),  # rejected
        _make_req("REQ-A9", method=VerificationMethod.ANALYSIS),  # awaiting non-test
        _make_req("REQ-A10", method=VerificationMethod.ANALYSIS), # verified by waiver
        _make_req("REQ-INFO-1", is_normative=False),
        _make_req("REQ-INFO-2", is_normative=False),
    ]

    tests = [
        _make_test("t_1", TestVerdict.PASSED),
        _make_test("t_2", TestVerdict.PASSED),
        _make_test("t_3", TestVerdict.FAILED),
        _make_test("t_4", TestVerdict.SKIPPED),
        _make_test("t_5", TestVerdict.UNEXECUTED),
        _make_test("t_7", TestVerdict.PASSED),
        _make_test("t_8", TestVerdict.PASSED),
        _make_test("t_rogue_1", TestVerdict.PASSED),  # Rogue test
    ]

    links = [
        _make_link("REQ-A1", "t_1", review_status=ReviewStatus.APPROVED),
        _make_link("REQ-A2", "t_2", review_status=ReviewStatus.UNREVIEWED),
        _make_link("REQ-A3", "t_3", review_status=ReviewStatus.APPROVED),
        _make_link("REQ-A4", "t_4", review_status=ReviewStatus.APPROVED),
        _make_link("REQ-A5", "t_5", review_status=ReviewStatus.APPROVED),
        _make_link("REQ-A7", "t_7", confidence=LinkConfidence.HIGH, review_status=ReviewStatus.UNREVIEWED),
        _make_link("REQ-A8", "t_8", review_status=ReviewStatus.REJECTED),
    ]

    reviews = {
        "REQ-A10": ReviewEvent(
            req_id="REQ-A10",
            status=ReviewStatus.WAIVED_ANALYSIS,
            reviewed_by="analyst",
            reference_doc="DOC-FEA",
        )
    }

    report = evaluate_workspace_status(reqs, tests, links, reviews)

    # Normative counts
    assert report.total_requirements == 12
    assert report.total_normative == 10
    assert report.non_normative_count == 2
    assert report.verified_count == 2       # A1 and A10
    assert report.linked_passing_count == 1 # A2
    assert report.unverified_gaps == 7      # A3, A4, A5, A6, A7, A8, A9

    # Strict Invariant 1: total_normative == verified + linked_passing + gaps
    assert report.total_normative == report.verified_count + report.linked_passing_count + report.unverified_gaps

    # Strict Invariant 2: sum(gap_reasons) == unverified_gaps
    assert sum(report.gap_reasons.values()) == report.unverified_gaps

    # Rogue tests
    assert report.rogue_tests_unlinked == 1  # t_rogue_1

    # Coverages
    assert report.audit_verified_coverage_pct == 20.0     # 2 / 10
    assert report.engineering_pass_coverage_pct == 30.0   # (2 + 1) / 10


def test_scenario_27_precedence_order_sequence() -> None:
    # Validate the exact order indices
    assert PRECEDENCE_ORDER[0] == UnverifiedReasonCode.TEST_EXECUTION_FAILED
    assert PRECEDENCE_ORDER[1] == UnverifiedReasonCode.TEST_EXECUTION_SKIPPED
    assert PRECEDENCE_ORDER[2] == UnverifiedReasonCode.TEST_UNEXECUTED
    assert PRECEDENCE_ORDER[3] == UnverifiedReasonCode.NO_ASSERTIONS
    assert PRECEDENCE_ORDER[4] == UnverifiedReasonCode.EXECUTION_STALE
    assert PRECEDENCE_ORDER[5] == UnverifiedReasonCode.REVIEW_STALE


def test_scenario_28_candidate_plus_rejected_shows_candidate_pending() -> None:
    req = _make_req("REQ-28")
    t1 = _make_test("t_28a", TestVerdict.PASSED)
    t2 = _make_test("t_28b", TestVerdict.PASSED)
    l1 = _make_link("REQ-28", "t_28a", review_status=ReviewStatus.REJECTED)
    l2 = _make_link("REQ-28", "t_28b", confidence=LinkConfidence.HIGH, review_status=ReviewStatus.UNREVIEWED)

    report = evaluate_workspace_status([req], [t1, t2], [l1, l2])
    assert report.requirement_results["REQ-28"].primary_reason == UnverifiedReasonCode.CANDIDATES_PENDING_REVIEW

