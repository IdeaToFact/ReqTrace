# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
CSV Exporter for Requirements Traceability Matrix (RTM).
Generates an audit-ready tabular matrix.
"""

import csv
from pathlib import Path
from typing import Dict, List, Optional
from reqtrace.models.requirement import Requirement
from reqtrace.models.trace_link import TraceLink


class CSVRTMExporter:
    HEADERS = [
        "Requirement ID",
        "Requirement Title",
        "Level",
        "Normative",
        "Parent Allocations",
        "Linked Test ID",
        "Assertion Span",
        "Execution Status",
        "Confidence",
        "Confidence Score",
        "Review Status",
        "Reviewed By",
        "Review Comment",
        "Is Stale",
        "Live Verified",
    ]

    def export(
        self,
        requirements: List[Requirement],
        links: List[TraceLink],
        output_file: Path | str,
    ) -> Path:
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        req_map: Dict[str, Requirement] = {r.id: r for r in requirements}
        # Group links by req_id
        links_by_req: Dict[str, List[TraceLink]] = {}
        for link in links:
            links_by_req.setdefault(link.req_id, []).append(link)

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self.HEADERS)

            for req in requirements:
                req_links = links_by_req.get(req.id, [])
                parents_str = "; ".join(req.parent_ids)

                if not req_links:
                    # Orphan requirement row
                    writer.writerow([
                        req.id,
                        req.title,
                        req.level.value,
                        "Yes" if req.is_normative else "No",
                        parents_str,
                        "[ORPHAN - NO TEST]",
                        "",
                        "UNEXECUTED",
                        "NONE",
                        "0.00",
                        "PENDING",
                        "",
                        "",
                        "No",
                        "FALSE",
                    ])
                else:
                    for link in req_links:
                        writer.writerow([
                            req.id,
                            req.title,
                            req.level.value,
                            "Yes" if req.is_normative else "No",
                            parents_str,
                            link.test_id,
                            link.evidence_span,
                            "PASSED" if link.is_verified else "UNVERIFIED",
                            link.confidence.value.upper(),
                            f"{link.confidence_score:.2f}",
                            link.review_status.value.upper(),
                            link.reviewed_by or "",
                            link.review_comment or "",
                            "YES" if link.is_stale else "No",
                            "TRUE" if link.is_verified else "FALSE",
                        ])

        return out_path

