# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Gap and Orphan Auditor for ReqTrace.
Computes bidirectional coverage and enforces CI quality gates:
1. Requirements with no tests (Orphan Requirements).
2. Tests with no requirements (Unlinked / Rogue Tests).
3. Requirements with failing test executions (Unverified Gaps).
4. Stale trace links from modified requirements.
"""

from typing import List, Set
from reqtrace.config import ThresholdsConfig, load_config
from reqtrace.models.requirement import Requirement
from reqtrace.models.rtm import GapAnalysisResult
from reqtrace.models.test_artifact import TestArtifact, TestExecutionStatus
from reqtrace.models.trace_link import TraceLink


class GapAuditor:
    def __init__(self, thresholds: ThresholdsConfig | None = None) -> None:
        self.thresholds = thresholds or load_config().thresholds

    def analyze(
        self,
        requirements: List[Requirement],
        tests: List[TestArtifact],
        links: List[TraceLink],
    ) -> GapAnalysisResult:
        normative_reqs = [r for r in requirements if r.is_normative]
        total_reqs = len(requirements)
        total_normative = len(normative_reqs)
        total_tests = len(tests)

        # 1. Map verified and linked requirement IDs
        linked_req_ids: Set[str] = {l.req_id for l in links}
        verified_req_ids: Set[str] = {l.req_id for l in links if l.is_verified}

        # 2. Orphan requirements (normative requirements without a verified passing test)
        orphan_reqs: List[str] = [
            r.id for r in normative_reqs if r.id not in verified_req_ids
        ]

        # 3. Unlinked tests (tests with no requirement links)
        linked_test_ids: Set[str] = {l.test_id for l in links}
        unlinked_tests: List[str] = [
            t.id for t in tests if t.id not in linked_test_ids
        ]

        # 4. Failed tests in execution
        failed_tests: List[str] = [
            t.id for t in tests if t.execution_status == TestExecutionStatus.FAILED
        ]

        # 5. Stale links
        stale_links: List[str] = [
            f"{l.req_id} ➔ {l.test_id}" for l in links if l.is_stale
        ]

        # 6. Compute coverage
        covered_count = len(verified_req_ids.intersection({r.id for r in normative_reqs}))
        coverage_pct = (
            (covered_count / total_normative) * 100.0 if total_normative > 0 else 100.0
        )

        # 7. Evaluate CI Gating Errors
        gating_errors: List[str] = []
        if coverage_pct < self.thresholds.min_coverage_pct:
            gating_errors.append(
                f"Coverage {coverage_pct:.1f}% is below required threshold {self.thresholds.min_coverage_pct:.1f}%"
            )
        if self.thresholds.fail_on_orphans and orphan_reqs:
            gating_errors.append(f"Found {len(orphan_reqs)} orphan requirements without passing tests: {', '.join(orphan_reqs[:5])}")
        if self.thresholds.fail_on_test_failures and failed_tests:
            gating_errors.append(f"Found {len(failed_tests)} failing tests in verification run: {', '.join(failed_tests[:5])}")
        if self.thresholds.fail_on_stale_reviews and stale_links:
            gating_errors.append(f"Found {len(stale_links)} stale links requiring re-review: {', '.join(stale_links[:5])}")

        is_passing = (len(gating_errors) == 0)

        return GapAnalysisResult(
            total_requirements=total_reqs,
            normative_requirements=total_normative,
            covered_requirements=covered_count,
            orphan_requirements=orphan_reqs,
            total_tests=total_tests,
            unlinked_tests=unlinked_tests,
            failed_tests=failed_tests,
            stale_links=stale_links,
            coverage_percentage=round(coverage_pct, 2),
            is_passing=is_passing,
            gating_errors=gating_errors,
        )

