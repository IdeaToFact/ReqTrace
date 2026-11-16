# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for ReqIFExporter.
"""

from pathlib import Path
from reqtrace.models.requirement import Requirement
from reqtrace.models.trace_link import LinkConfidence, TraceLink
from reqtrace.reports.reqif_exporter import ReqIFExporter
from reqtrace.parsers.reqif_parser import ReqIFParser


def test_reqif_export_and_reingest(tmp_path: Path) -> None:
    req1 = Requirement(id="SYS-01", title="System Req", description="State estimation", source_file="s.reqif")
    req2 = Requirement(id="HLR-01", title="High Level Req", description="Dead reckoning", parent_ids=["SYS-01"], source_file="s.reqif")

    link = TraceLink(
        req_id="HLR-01",
        test_id="test_nav.py::test_case",
        confidence=LinkConfidence.VERIFIED,
        confidence_score=1.0,
        evidence_span="assert True",
        file_offset=(1, 5),
        justification="Verified",
        is_verified=True,
    )

    out_file = tmp_path / "exported.reqif"
    exporter = ReqIFExporter()
    exporter.export([req1, req2], [link], output_file=out_file)

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "REQ-IF" in content
    assert "SPEC-RELATION" in content
    assert "rel_alloc_HLR-01_SYS-01" in content
    assert "test_nav.py::test_case" in content

    # Re-ingest with ReqIFParser to verify standard XML compliance
    parser = ReqIFParser()
    reparsed = parser.parse(out_file)
    assert len(reparsed) == 2
    hlr = next(r for r in reparsed if r.id == "HLR-01")
    assert hlr.parent_ids == ["SYS-01"]

