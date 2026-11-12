# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Tests for DocxSpecificationParser.
"""

from pathlib import Path
import docx
import pytest

from reqtrace.parsers.docx_parser import DocxSpecificationParser
from reqtrace.models.requirement import RequirementLevel


def test_docx_parser_extracts_tables_and_paragraphs(tmp_path: Path):
    doc_path = tmp_path / "spec_test.docx"
    doc = docx.Document()

    # Add headings and paragraph requirements
    doc.add_heading("1.0 Navigation System", level=1)
    doc.add_heading("1.1 GPS Unit", level=2)
    doc.add_paragraph("REQ-NAV-001: The system shall acquire a valid GPS fix within 2.5 seconds of antenna lock.")

    # Add structured requirements table
    table = doc.add_table(rows=1, cols=4)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Requirement ID"
    hdr_cells[1].text = "Title"
    hdr_cells[2].text = "Level"
    hdr_cells[3].text = "Description"

    row1 = table.add_row().cells
    row1[0].text = "REQ-NAV-002"
    row1[1].text = "GPS Loss Failover"
    row1[2].text = "High-Level"
    row1[3].text = "The system shall switch to inertial navigation upon GPS signal loss."

    row2 = table.add_row().cells
    row2[0].text = "REQ-NAV-003"
    row2[1].text = "Coordinate Translation"
    row2[2].text = "Low-Level"
    row2[3].text = "The system shall output ECEF coordinates at 50 Hz."

    doc.save(doc_path)

    parser = DocxSpecificationParser()
    reqs = parser.parse(doc_path)

    assert len(reqs) == 3
    req_map = {r.id: r for r in reqs}

    assert "REQ-NAV-001" in req_map
    assert "REQ-NAV-002" in req_map
    assert "REQ-NAV-003" in req_map

    # Check paragraph extraction
    assert "GPS fix within 2.5 seconds" in req_map["REQ-NAV-001"].description
    assert req_map["REQ-NAV-001"].attributes.get("section") == "1.1 GPS Unit"

    # Check table extraction and level inference
    assert req_map["REQ-NAV-002"].level == RequirementLevel.HIGH_LEVEL
    assert "inertial navigation" in req_map["REQ-NAV-002"].description
    assert req_map["REQ-NAV-003"].level == RequirementLevel.LOW_LEVEL
    assert "ECEF coordinates" in req_map["REQ-NAV-003"].description
