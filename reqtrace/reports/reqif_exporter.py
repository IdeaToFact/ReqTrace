# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Enriched ReqIF Exporter for ReqTrace.
Exports requirement specifications and generated trace links as standard ReqIF XML
with <SPEC-RELATION> elements for direct re-import into IBM DOORS, Siemens Polarion,
and Jama without proprietary ALM plugins.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import List
import xml.etree.ElementTree as ET
from xml.dom import minidom

from reqtrace.models.requirement import Requirement
from reqtrace.models.trace_link import TraceLink


class ReqIFExporter:
    REQIF_NS = "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"

    def export(
        self,
        requirements: List[Requirement],
        links: List[TraceLink],
        output_file: Path | str = "enriched_trace.reqif",
    ) -> Path:
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        root = ET.Element("REQ-IF", xmlns=self.REQIF_NS)
        header = ET.SubElement(root, "THE-HEADER")
        reqif_header = ET.SubElement(
            header,
            "REQ-IF-HEADER",
            IDENTIFIER="reqtrace_header",
            CREATION_TIME=datetime.now(timezone.utc).isoformat(),
            REQ_IF_TOOL_ID="ReqTrace Community Edition v0.1.0",
            TITLE="Requirements Traceability and Verification Package",
        )

        core_content = ET.SubElement(root, "CORE-CONTENT")
        reqif_content = ET.SubElement(core_content, "REQ-IF-CONTENT")

        # Spec Types
        spec_types = ET.SubElement(reqif_content, "SPEC-TYPES")
        spec_obj_type = ET.SubElement(
            spec_types,
            "SPEC-OBJECT-TYPE",
            IDENTIFIER="type_requirement",
        )
        spec_obj_type.set("LONG-NAME", "Requirement")
        spec_attrs = ET.SubElement(spec_obj_type, "SPEC-ATTRIBUTES")
        
        attr1 = ET.SubElement(spec_attrs, "ATTRIBUTE-DEFINITION-STRING", IDENTIFIER="attr_id")
        attr1.set("LONG-NAME", "Customer_Req_Number")
        attr2 = ET.SubElement(spec_attrs, "ATTRIBUTE-DEFINITION-STRING", IDENTIFIER="attr_title")
        attr2.set("LONG-NAME", "ReqIF.Name")
        attr3 = ET.SubElement(spec_attrs, "ATTRIBUTE-DEFINITION-STRING", IDENTIFIER="attr_desc")
        attr3.set("LONG-NAME", "ReqIF.Text")
        attr4 = ET.SubElement(spec_attrs, "ATTRIBUTE-DEFINITION-STRING", IDENTIFIER="attr_level")
        attr4.set("LONG-NAME", "Requirement Level")

        # Spec Objects
        spec_objects = ET.SubElement(reqif_content, "SPEC-OBJECTS")
        for req in requirements:
            spec_obj = ET.SubElement(spec_objects, "SPEC-OBJECT", IDENTIFIER=f"req_{req.id}")
            spec_obj.set("LAST-CHANGE", datetime.now(timezone.utc).isoformat())
            values = ET.SubElement(spec_obj, "VALUES")

            v_id = ET.SubElement(values, "ATTRIBUTE-VALUE-STRING")
            v_id.set("THE-VALUE", req.id)
            d_id = ET.SubElement(v_id, "DEFINITION")
            ET.SubElement(d_id, "ATTRIBUTE-DEFINITION-STRING-REF").text = "attr_id"

            v_title = ET.SubElement(values, "ATTRIBUTE-VALUE-STRING")
            v_title.set("THE-VALUE", req.title)
            d_title = ET.SubElement(v_title, "DEFINITION")
            ET.SubElement(d_title, "ATTRIBUTE-DEFINITION-STRING-REF").text = "attr_title"

            v_desc = ET.SubElement(values, "ATTRIBUTE-VALUE-STRING")
            v_desc.set("THE-VALUE", req.description)
            d_desc = ET.SubElement(v_desc, "DEFINITION")
            ET.SubElement(d_desc, "ATTRIBUTE-DEFINITION-STRING-REF").text = "attr_desc"

            v_level = ET.SubElement(values, "ATTRIBUTE-VALUE-STRING")
            v_level.set("THE-VALUE", req.level.value)
            d_level = ET.SubElement(v_level, "DEFINITION")
            ET.SubElement(d_level, "ATTRIBUTE-DEFINITION-STRING-REF").text = "attr_level"

        # Spec Relations (Parent allocations and test links)
        spec_relations = ET.SubElement(reqif_content, "SPEC-RELATIONS")
        
        # 1. Parent allocation relations
        for req in requirements:
            for parent_id in req.parent_ids:
                rel = ET.SubElement(spec_relations, "SPEC-RELATION", IDENTIFIER=f"rel_alloc_{req.id}_{parent_id}")
                src = ET.SubElement(rel, "SOURCE")
                ET.SubElement(src, "SPEC-OBJECT-REF").text = f"req_{req.id}"
                tgt = ET.SubElement(rel, "TARGET")
                ET.SubElement(tgt, "SPEC-OBJECT-REF").text = f"req_{parent_id}"

        # 2. Test trace links
        for idx, link in enumerate(links):
            rel = ET.SubElement(spec_relations, "SPEC-RELATION", IDENTIFIER=f"rel_trace_{idx + 1}")
            src = ET.SubElement(rel, "SOURCE")
            ET.SubElement(src, "SPEC-OBJECT-REF").text = f"req_{link.req_id}"
            tgt = ET.SubElement(rel, "TARGET")
            # Encapsulate verified test info in TARGET ref
            ET.SubElement(tgt, "SPEC-OBJECT-REF").text = link.test_id

        # Pretty-print and save
        xml_str = ET.tostring(root, encoding="utf-8")
        parsed = minidom.parseString(xml_str)
        pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")

        with open(out_path, "wb") as f:
            f.write(pretty_xml)

        return out_path
