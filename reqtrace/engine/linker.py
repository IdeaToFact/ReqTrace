# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unified Trace Linker for ReqTrace.
Orchestrates deterministic tag resolution, fuzzy window alignment,
persistent review state overlay, and dynamic Live Verification.
"""

from typing import Dict, List, Optional
from reqtrace.analysis.review_store import ReviewStore
from reqtrace.engine.confidence import ConfidenceCalibrator
from reqtrace.engine.fuzzy_window import FuzzyWindowAligner
from reqtrace.engine.tag_matcher import DeterministicTagMatcher
from reqtrace.models.requirement import Requirement
from reqtrace.models.test_artifact import TestArtifact, TestExecutionStatus
from reqtrace.models.trace_link import (
    LinkConfidence,
    ReviewStatus,
    TraceLink,
)


class TraceLinker:
    def __init__(
        self,
        high_threshold: float = 0.85,
        medium_threshold: float = 0.60,
        review_store: Optional[ReviewStore] = None,
    ) -> None:
        self.calibrator = ConfidenceCalibrator(high_threshold, medium_threshold)
        self.review_store = review_store or ReviewStore()

    def link(
        self,
        requirements: List[Requirement],
        tests: List[TestArtifact],
    ) -> List[TraceLink]:
        """
        Computes trace links between requirements and test artifacts.
        1. Exact tag resolution via DeterministicTagMatcher (100% confidence).
        2. Fuzzy assertion alignment via FuzzyWindowAligner.
        3. Merges persistent human reviews and evaluates staleness.
        4. Sets live verification status: verified iff test passed in CI.
        """
        req_map: Dict[str, Requirement] = {r.id: r for r in requirements}
        test_map: Dict[str, TestArtifact] = {t.id: t for t in tests}

        # 1. Deterministic Tag Matching
        candidate_links = DeterministicTagMatcher.match(req_map, tests)

        # 2. Fuzzy Semantic Linking for unlinked requirements
        linked_req_ids = {l.req_id for l in candidate_links}
        for req in requirements:
            if not req.is_normative or req.id in linked_req_ids:
                continue

            best_test: Optional[TestArtifact] = None
            best_score: float = 0.0
            best_evidence: str = ""

            req_query = f"{req.title} {req.description}".lower()

            for test in tests:
                for assertion in test.assertion_statements:
                    score = FuzzyWindowAligner.match_score(req_query, assertion)
                    if score > best_score:
                        best_score = score
                        best_test = test
                        best_evidence = assertion

                func_name = test.id.split("::")[-1].replace("_", " ")
                score = FuzzyWindowAligner.match_score(req.title, func_name)
                if score > best_score:
                    best_score = score
                    best_test = test
                    best_evidence = test.assertion_statements[0] if test.assertion_statements else test.id

            if best_test and best_score >= self.calibrator.medium_threshold:
                conf = self.calibrator.calibrate(best_score)
                link = TraceLink(
                    req_id=req.id,
                    test_id=best_test.id,
                    confidence=conf,
                    confidence_score=round(best_score, 4),
                    evidence_span=best_evidence,
                    file_offset=(best_test.line_start, best_test.line_end),
                    justification=f"Fuzzy assertion match (score: {best_score:.2f}) on '{best_evidence}'",
                    is_verified=(best_test.execution_status == TestExecutionStatus.PASSED),
                )
                candidate_links.append(link)

        # 3. Apply persistent human reviews overlay from ReviewStore
        merged_links = self.review_store.apply_overlay(candidate_links, req_map)

        # 4. Final verification status: test must be PASSED and human review must NOT be REJECTED
        for link in merged_links:
            t_art = test_map.get(link.test_id)
            if t_art:
                has_passed = (t_art.execution_status == TestExecutionStatus.PASSED)
                is_not_rejected = (link.review_status != ReviewStatus.REJECTED)
                link.is_verified = (has_passed and is_not_rejected)
            else:
                link.is_verified = False

        return merged_links
