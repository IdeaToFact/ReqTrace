# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for CSVParser.
"""

from pathlib import Path
from reqtrace.parsers.csv_parser import CSVParser
from reqtrace.models.requirement import RequirementLevel


def test_parse_csv_matrix(tmp_path: Path) -> None:
    csv_content = """Req ID,Req Title,Statement,Req Level,Allocated_From,Normative?
REQ-PWR-001,Power Bus Voltage,The power bus shall maintain 28V +/- 2V.,System,SYS-REQ-01,true
REQ-PWR-002,Battery Backup,The backup battery shall provide 30 minutes of operational power.,Low-Level,"REQ-PWR-001; SYS-REQ-02",true
NOTE-PWR-01,Design Rationale,Refer to battery spec rev 4.,Info,,false
"""
    csv_file = tmp_path / "matrix.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    parser = CSVParser()
    requirements = parser.parse(csv_file)
    assert len(requirements) == 3

    req1 = next(r for r in requirements if r.id == "REQ-PWR-001")
    assert req1.title == "Power Bus Voltage"
    assert "28V +/- 2V" in req1.description
    assert req1.level == RequirementLevel.SYSTEM
    assert req1.parent_ids == ["SYS-REQ-01"]
    assert req1.is_normative is True

    req2 = next(r for r in requirements if r.id == "REQ-PWR-002")
    assert req2.level == RequirementLevel.LOW_LEVEL
    assert set(req2.parent_ids) == {"REQ-PWR-001", "SYS-REQ-02"}

    note = next(r for r in requirements if r.id == "NOTE-PWR-01")
    assert note.is_normative is False

