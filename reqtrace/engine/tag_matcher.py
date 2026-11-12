# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Deterministic Tag and Symbol Matcher for ReqTrace.
Matches declared requirement references in test fixtures with 100% confidence.
"""

from typing import Dict, List
from reqtrace.models.requirement import Requirement
from reqtrace.models.test_artifact import TestArtifact
from reqtrace.models.trace_link import LinkConfidence, TraceLink


class DeterministicTagMatcher:
    @staticmethod
    def match(
        requirements_map: Dict[str, Requirement],
        tests: List[TestArtifact],
    ) -> List[TraceLink]:
        links: List[TraceLink] = []

        for test in tests:
            for ref_id in test.declared_req_refs:
                if ref_id in requirements_map:
                    req = requirements_map[ref_id]
                    evidence = (
                        test.assertion_statements[0]
                        if test.assertion_statements
                        else f"def {test.id}"
                    )
                    link = TraceLink(
                        req_id=req.id,
                        test_id=test.id,
                        confidence=LinkConfidence.VERIFIED,
                        confidence_score=1.0,
                        evidence_span=evidence,
                        file_offset=(test.line_start, test.line_end),
                        justification=f"Explicit reference @pytest.mark.req('{req.id}') with assertions: {'; '.join(test.assertion_statements) or 'None'}",
                        is_verified=False,  # Set by linker based on dynamic test execution
                    )
                    links.append(link)

        return links

