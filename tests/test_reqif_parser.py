# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for ReqIFParser.
Verifies parsing of standard DOORS/ReqIF XML with custom attributes and relations.
"""

from pathlib import Path
from reqtrace.config import ReqIFMappingConfig
from reqtrace.parsers.reqif_parser import ReqIFParser
from reqtrace.models.requirement import RequirementLevel


SAMPLE_REQIF_XML = """<?xml version="1.0" encoding="UTF-8"?>
<REQ-IF xmlns="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd">
  <CORE-CONTENT>
    <REQ-IF-CONTENT>
      <SPEC-TYPES>
        <SPEC-OBJECT-TYPE IDENTIFIER="type_req" LONG-NAME="Requirement Type">
          <SPEC-ATTRIBUTES>
            <ATTRIBUTE-DEFINITION-STRING IDENTIFIER="attr_id" LONG-NAME="Customer_Req_Number"/>
            <ATTRIBUTE-DEFINITION-XHTML IDENTIFIER="attr_text" LONG-NAME="ReqIF.Text"/>
            <ATTRIBUTE-DEFINITION-STRING IDENTIFIER="attr_type" LONG-NAME="Object Type"/>
            <ATTRIBUTE-DEFINITION-STRING IDENTIFIER="attr_level" LONG-NAME="Requirement Level"/>
          </SPEC-ATTRIBUTES>
        </SPEC-OBJECT-TYPE>
      </SPEC-TYPES>
      <SPEC-OBJECTS>
        <SPEC-OBJECT IDENTIFIER="obj_001" LAST-CHANGE="2026-11-01T12:00:00Z">
          <VALUES>
            <ATTRIBUTE-VALUE-STRING THE-VALUE="Section 1: Navigation">
              <DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>attr_text</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION>
            </ATTRIBUTE-VALUE-STRING>
            <ATTRIBUTE-VALUE-STRING THE-VALUE="HEADING-01">
              <DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>attr_id</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION>
            </ATTRIBUTE-VALUE-STRING>
            <ATTRIBUTE-VALUE-STRING THE-VALUE="Heading">
              <DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>attr_type</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION>
            </ATTRIBUTE-VALUE-STRING>
          </VALUES>
        </SPEC-OBJECT>
        <SPEC-OBJECT IDENTIFIER="obj_002" LAST-CHANGE="2026-11-01T12:00:00Z">
          <VALUES>
            <ATTRIBUTE-VALUE-STRING THE-VALUE="REQ-NAV-0104">
              <DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>attr_id</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION>
            </ATTRIBUTE-VALUE-STRING>
            <ATTRIBUTE-VALUE-STRING THE-VALUE="Requirement">
              <DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>attr_type</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION>
            </ATTRIBUTE-VALUE-STRING>
            <ATTRIBUTE-VALUE-STRING THE-VALUE="High-Level">
              <DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>attr_level</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION>
            </ATTRIBUTE-VALUE-STRING>
            <ATTRIBUTE-VALUE-XHTML>
              <THE-VALUE><div><p>The navigation system <b>shall switch</b> to inertial dead-reckoning within 200ms of GPS loss.</p></div></THE-VALUE>
              <DEFINITION><ATTRIBUTE-DEFINITION-XHTML-REF>attr_text</ATTRIBUTE-DEFINITION-XHTML-REF></DEFINITION>
            </ATTRIBUTE-VALUE-XHTML>
          </VALUES>
        </SPEC-OBJECT>
      </SPEC-OBJECTS>
      <SPEC-RELATIONS>
        <SPEC-RELATION IDENTIFIER="rel_01">
          <SOURCE><SPEC-OBJECT-REF>obj_002</SPEC-OBJECT-REF></SOURCE>
          <TARGET><SPEC-OBJECT-REF>SYS-REQ-NAV-01</SPEC-OBJECT-REF></TARGET>
        </SPEC-RELATION>
      </SPEC-RELATIONS>
    </REQ-IF-CONTENT>
  </CORE-CONTENT>
</REQ-IF>
"""


def test_parse_sample_reqif(tmp_path: Path) -> None:
    reqif_file = tmp_path / "sample.reqif"
    reqif_file.write_text(SAMPLE_REQIF_XML, encoding="utf-8")

    parser = ReqIFParser(
        mapping_config=ReqIFMappingConfig(
            id_attribute="Customer_Req_Number",
            text_attribute="ReqIF.Text",
            type_attribute="Object Type",
            normative_value="Requirement",
            level_attribute="Requirement Level",
        )
    )

    requirements = parser.parse(reqif_file)
    assert len(requirements) == 2

    # Heading object
    heading = next(r for r in requirements if r.id == "HEADING-01")
    assert heading.is_normative is False

    # Normative requirement
    req = next(r for r in requirements if r.id == "REQ-NAV-0104")
    assert req.is_normative is True
    assert req.level == RequirementLevel.HIGH_LEVEL
    assert "shall switch to inertial dead-reckoning within 200ms" in req.description
    assert "<p>" not in req.description
    assert req.parent_ids == ["SYS-REQ-NAV-01"]
    assert len(req.sha256) == 64

