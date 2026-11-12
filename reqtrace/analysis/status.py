# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Canonical Status & Precedence Model for ReqTrace.
Provides deterministic, table-driven two-axis verification evaluation,
multi-link conjunctive (All-Must-Pass) aggregation, and partitioned gap diagnostics.
"""

from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from reqtrace.models.requirement import Requirement, VerificationMethod
from reqtrace.models.test_artifact import TestArtifact, TestVerdict
from reqtrace.models.trace_link import (
    LinkConfidence,
    ReviewEvent,
    ReviewStatus,
    TraceLink,
    VerificationStatus,
)


class UnverifiedReasonCode(str, Enum):
    ORPHAN_NO_TEST = "orphan_no_test"
    CANDIDATES_PENDING_REVIEW = "candidates_pending_review"
    ALL_LINKS_REJECTED = "all_links_rejected"
    AWAITING_NON_TEST_VERIFICATION = "awaiting_non_test_verification"
    TEST_EXECUTION_FAILED = "test_execution_failed"
    TEST_EXECUTION_SKIPPED = "test_execution_skipped"
    TEST_UNEXECUTED = "test_unexecuted"
    NO_ASSERTIONS = "no_assertions"
    EXECUTION_STALE = "execution_stale"
    REVIEW_STALE = "review_stale"


class RequirementStatusResult(BaseModel):
    req_id: str
    is_normative: bool
    verification_method: VerificationMethod
    verification_status: VerificationStatus
    primary_reason: Optional[UnverifiedReasonCode] = None
    all_reasons: List[UnverifiedReasonCode] = Field(default_factory=list)
    active_links_count: int = 0
    candidate_links_count: int = 0
    rejected_links_count: int = 0


class WorkspaceStatusReport(BaseModel):
    total_requirements: int
    total_normative: int
    non_normative_count: int
    verified_count: int
    linked_passing_count: int
    unverified_gaps: int
    gap_reasons: Dict[UnverifiedReasonCode, int]
    rogue_tests_unlinked: int
    audit_verified_coverage_pct: float
    engineering_pass_coverage_pct: float
    requirement_results: Dict[str, RequirementStatusResult]


# Deterministic Precedence Ranking for Gap Reasons across active links
# Earlier index = higher precedence
PRECEDENCE_ORDER = [
    UnverifiedReasonCode.TEST_EXECUTION_FAILED,
    UnverifiedReasonCode.TEST_EXECUTION_SKIPPED,
    UnverifiedReasonCode.TEST_UNEXECUTED,
    UnverifiedReasonCode.NO_ASSERTIONS,
    UnverifiedReasonCode.EXECUTION_STALE,
    UnverifiedReasonCode.REVIEW_STALE,
    UnverifiedReasonCode.ALL_LINKS_REJECTED,
    UnverifiedReasonCode.CANDIDATES_PENDING_REVIEW,
    UnverifiedReasonCode.AWAITING_NON_TEST_VERIFICATION,
    UnverifiedReasonCode.ORPHAN_NO_TEST,
]


def evaluate_workspace_status(
    requirements: List[Requirement],
    tests: List[TestArtifact],
    links: List[TraceLink],
    reviews: Optional[Dict[str, ReviewEvent]] = None,
) -> WorkspaceStatusReport:
    """
    Evaluates requirements, test artifacts, trace links, and reviews into
    a strictly partitioned, mathematically consistent audit status report.
    """
    reviews_map = reviews or {}
    test_map: Dict[str, TestArtifact] = {t.id: t for t in tests}

    # Group links by requirement ID
    req_to_links: Dict[str, List[TraceLink]] = {r.id: [] for r in requirements}
    for link in links:
        if link.req_id in req_to_links:
            req_to_links[link.req_id].append(link)

    # Track linked tests for rogue/unlinked test identification
    linked_test_ids: Set[str] = {link.test_id for link in links if link.test_id}
    rogue_tests_unlinked = len([t for t in tests if t.id not in linked_test_ids])

    # Counters
    non_normative_count = 0
    verified_count = 0
    linked_passing_count = 0
    unverified_gaps = 0

    gap_reasons: Dict[UnverifiedReasonCode, int] = {
        code: 0 for code in UnverifiedReasonCode
    }
    requirement_results: Dict[str, RequirementStatusResult] = {}

    for req in requirements:
        # 1. Non-normative filter
        if not req.is_normative:
            non_normative_count += 1
            requirement_results[req.id] = RequirementStatusResult(
                req_id=req.id,
                is_normative=False,
                verification_method=req.verification_method,
                verification_status=VerificationStatus.UNVERIFIED_GAP,
                primary_reason=None,
            )
            continue

        # 2. Check for requirement-level waiver (e.g. analysis/inspection)
        req_review = reviews_map.get(req.id)
        if req.verification_method != VerificationMethod.TEST:
            if req_review and req_review.status == ReviewStatus.WAIVED_ANALYSIS:
                verified_count += 1
                requirement_results[req.id] = RequirementStatusResult(
                    req_id=req.id,
                    is_normative=True,
                    verification_method=req.verification_method,
                    verification_status=VerificationStatus.VERIFIED,
                    primary_reason=None,
                )
            elif req_review and req_review.status == ReviewStatus.REJECTED:
                unverified_gaps += 1
                reason = UnverifiedReasonCode.ALL_LINKS_REJECTED
                gap_reasons[reason] += 1
                requirement_results[req.id] = RequirementStatusResult(
                    req_id=req.id,
                    is_normative=True,
                    verification_method=req.verification_method,
                    verification_status=VerificationStatus.UNVERIFIED_GAP,
                    primary_reason=reason,
                    all_reasons=[reason],
                )
            else:
                unverified_gaps += 1
                reason = UnverifiedReasonCode.AWAITING_NON_TEST_VERIFICATION
                gap_reasons[reason] += 1
                requirement_results[req.id] = RequirementStatusResult(
                    req_id=req.id,
                    is_normative=True,
                    verification_method=req.verification_method,
                    verification_status=VerificationStatus.UNVERIFIED_GAP,
                    primary_reason=reason,
                    all_reasons=[reason],
                )
            continue

        # 3. For verification_method == TEST: partition links into active, candidate, and rejected
        req_links = req_to_links.get(req.id, [])
        active_links: List[TraceLink] = []
        candidate_links: List[TraceLink] = []
        rejected_links: List[TraceLink] = []

        for link in req_links:
            if link.review_status == ReviewStatus.REJECTED:
                rejected_links.append(link)
            elif link.confidence == LinkConfidence.EXPLICIT_TAG or link.review_status == ReviewStatus.APPROVED:
                active_links.append(link)
            else:
                # Fuzzy link not yet approved => candidate only (zero coverage)
                candidate_links.append(link)

        # 4. Handle cases with zero active links
        if not active_links:
            unverified_gaps += 1
            if rejected_links and not candidate_links:
                reason = UnverifiedReasonCode.ALL_LINKS_REJECTED
            elif candidate_links:
                reason = UnverifiedReasonCode.CANDIDATES_PENDING_REVIEW
            else:
                reason = UnverifiedReasonCode.ORPHAN_NO_TEST

            gap_reasons[reason] += 1
            requirement_results[req.id] = RequirementStatusResult(
                req_id=req.id,
                is_normative=True,
                verification_method=req.verification_method,
                verification_status=VerificationStatus.UNVERIFIED_GAP,
                primary_reason=reason,
                all_reasons=[reason],
                active_links_count=0,
                candidate_links_count=len(candidate_links),
                rejected_links_count=len(rejected_links),
            )
            continue

        # 5. Evaluate active links under Conjunctive "All Must Pass" aggregation
        link_reasons: Set[UnverifiedReasonCode] = set()
        all_passed = True
        all_approved = True
        has_pending_review = False

        for link in active_links:
            test = test_map.get(link.test_id)
            if not test:
                link_reasons.add(UnverifiedReasonCode.TEST_UNEXECUTED)
                all_passed = False
                continue

            # Minimum evidence: affirmative assertions check
            if not test.has_assertions:
                link_reasons.add(UnverifiedReasonCode.NO_ASSERTIONS)
                all_passed = False

            # Test execution verdict
            if test.execution_status == TestVerdict.FAILED:
                link_reasons.add(UnverifiedReasonCode.TEST_EXECUTION_FAILED)
                all_passed = False
            elif test.execution_status == TestVerdict.SKIPPED:
                link_reasons.add(UnverifiedReasonCode.TEST_EXECUTION_SKIPPED)
                all_passed = False
            elif test.execution_status == TestVerdict.UNEXECUTED:
                link_reasons.add(UnverifiedReasonCode.TEST_UNEXECUTED)
                all_passed = False

            # Staleness checks
            if link.is_execution_stale:
                link_reasons.add(UnverifiedReasonCode.EXECUTION_STALE)
                all_passed = False

            if link.is_stale or link.review_status == ReviewStatus.STALE_REVIEW:
                link_reasons.add(UnverifiedReasonCode.REVIEW_STALE)

            # Review status
            if link.review_status in (ReviewStatus.UNREVIEWED, ReviewStatus.PENDING):
                has_pending_review = True
                all_approved = False
            elif link.review_status != ReviewStatus.APPROVED:
                all_approved = False

        # 6. Aggregate requirement status based on active link outcomes
        if link_reasons:
            # Active gap exists: pick highest-precedence primary reason
            primary = next(code for code in PRECEDENCE_ORDER if code in link_reasons)
            unverified_gaps += 1
            gap_reasons[primary] += 1
            requirement_results[req.id] = RequirementStatusResult(
                req_id=req.id,
                is_normative=True,
                verification_method=req.verification_method,
                verification_status=VerificationStatus.UNVERIFIED_GAP,
                primary_reason=primary,
                all_reasons=sorted(list(link_reasons), key=lambda c: PRECEDENCE_ORDER.index(c)),
                active_links_count=len(active_links),
                candidate_links_count=len(candidate_links),
                rejected_links_count=len(rejected_links),
            )
        elif all_passed and all_approved:
            # Formally verified
            verified_count += 1
            requirement_results[req.id] = RequirementStatusResult(
                req_id=req.id,
                is_normative=True,
                verification_method=req.verification_method,
                verification_status=VerificationStatus.VERIFIED,
                primary_reason=None,
                all_reasons=[],
                active_links_count=len(active_links),
                candidate_links_count=len(candidate_links),
                rejected_links_count=len(rejected_links),
            )
        else:
            # All active tests passed and execution is fresh, but human review is pending
            linked_passing_count += 1
            requirement_results[req.id] = RequirementStatusResult(
                req_id=req.id,
                is_normative=True,
                verification_method=req.verification_method,
                verification_status=VerificationStatus.LINKED_PASSING,
                primary_reason=None,
                all_reasons=[],
                active_links_count=len(active_links),
                candidate_links_count=len(candidate_links),
                rejected_links_count=len(rejected_links),
            )

    total_reqs = len(requirements)
    total_normative = total_reqs - non_normative_count

    # Coverage formulas over normative requirements
    audit_cov = (
        round((verified_count / total_normative) * 100.0, 2)
        if total_normative > 0
        else 100.0
    )
    eng_cov = (
        round(((verified_count + linked_passing_count) / total_normative) * 100.0, 2)
        if total_normative > 0
        else 100.0
    )

    # Mathematical Invariant Checks
    assert (
        total_normative == verified_count + linked_passing_count + unverified_gaps
    ), f"Invariant broken: {total_normative} != {verified_count} + {linked_passing_count} + {unverified_gaps}"

    assert (
        sum(gap_reasons.values()) == unverified_gaps
    ), f"Reason partition broken: sum={sum(gap_reasons.values())} != gaps={unverified_gaps}"

    return WorkspaceStatusReport(
        total_requirements=total_reqs,
        total_normative=total_normative,
        non_normative_count=non_normative_count,
        verified_count=verified_count,
        linked_passing_count=linked_passing_count,
        unverified_gaps=unverified_gaps,
        gap_reasons=gap_reasons,
        rogue_tests_unlinked=rogue_tests_unlinked,
        audit_verified_coverage_pct=audit_cov,
        engineering_pass_coverage_pct=eng_cov,
        requirement_results=requirement_results,
    )

