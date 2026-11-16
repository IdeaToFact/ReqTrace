# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
ReqIF (Requirements Interchange Format) XML parser.
Extracts SpecObjects, SpecRelations, attribute values, and hierarchical allocations
from standard ReqIF 1.0.1 / 1.2 XML specifications.
Uses defusedxml for secure, entity-expansion-protected parsing.
"""

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from xml.etree.ElementTree import Element

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from reqtrace.config import ReqIFMappingConfig, load_config
from reqtrace.models.requirement import (
    Requirement,
    RequirementLevel,
    RequirementType,
)
from reqtrace.parsers.xhtml_cleaner import XHTMLCleaner


def _strip_ns(tag: str) -> str:
    """Strips XML namespace prefix from a tag name, e.g. '{http://...}SPEC-OBJECT' -> 'SPEC-OBJECT'."""
    return tag.split("}")[-1] if "}" in tag else tag


class ReqIFParser:
    def __init__(self, mapping_config: Optional[ReqIFMappingConfig] = None) -> None:
        self.mapping = mapping_config or load_config().reqif_mapping

    def parse(self, file_path: Path | str) -> List[Requirement]:
        """
        Parses a ReqIF XML file and returns a list of validated Requirement instances.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"ReqIF file not found: {path}")

        tree = ET.parse(str(path))
        root = tree.getroot()

        # 1. Build map of attribute definitions: attr_def_id -> long_name
        attr_defs = self._extract_attribute_definitions(root)

        # 2. Extract relations: child_id -> set of parent_ids
        relations = self._extract_relations(root)

        # 3. Parse all SPEC-OBJECT elements
        requirements: List[Requirement] = []
        spec_objects = self._find_all_by_local_name(root, "SPEC-OBJECT")
        obj_to_req_id: Dict[str, str] = {}

        # First pass: map object internal IDENTIFIER to resolved customer requirement ID
        for obj in spec_objects:
            obj_id = obj.attrib.get("IDENTIFIER", "")
            attr_values = self._extract_object_attributes(obj, attr_defs)
            req_id = (
                attr_values.get(self.mapping.id_attribute)
                or attr_values.get("ReqIF.ForeignID")
                or attr_values.get("ID")
                or obj_id
            )
            if obj_id and req_id:
                obj_to_req_id[obj_id] = str(req_id).strip()

        for obj in spec_objects:
            obj_id = obj.attrib.get("IDENTIFIER", "")
            attr_values = self._extract_object_attributes(obj, attr_defs)

            # Resolve requirement ID from custom mapping or fallbacks
            req_id = (
                attr_values.get(self.mapping.id_attribute)
                or attr_values.get("ReqIF.ForeignID")
                or attr_values.get("ID")
                or obj_id
            )
            if not req_id:
                continue

            # Resolve description / text
            raw_text = (
                attr_values.get(self.mapping.text_attribute)
                or attr_values.get("ReqIF.Description")
                or attr_values.get("Description")
                or ""
            )
            cleaned_text = XHTMLCleaner.clean(raw_text)

            # Resolve title / name
            raw_title = (
                attr_values.get("ReqIF.Name")
                or attr_values.get("Name")
                or attr_values.get("Title")
                or ""
            )
            title = XHTMLCleaner.clean(raw_title) or (
                cleaned_text.split(".")[0].strip() if cleaned_text else req_id
            )

            # Determine whether requirement is normative ("shall") vs heading/informational
            obj_type = attr_values.get(self.mapping.type_attribute, "")
            is_normative = True
            if self.mapping.normative_value and obj_type:
                is_normative = obj_type.strip().lower() == self.mapping.normative_value.strip().lower()
            elif obj_type.lower() in {"heading", "header", "section", "comment", "note"}:
                is_normative = False

            # Determine level
            level_str = attr_values.get(self.mapping.level_attribute, "").lower()
            level = RequirementLevel.HIGH_LEVEL
            if "system" in level_str:
                level = RequirementLevel.SYSTEM
            elif "low" in level_str or "llr" in level_str:
                level = RequirementLevel.LOW_LEVEL
            elif "arch" in level_str:
                level = RequirementLevel.ARCHITECTURE

            # Resolve parents (either from foreign obj_id or req_id) and map internal identifiers to customer req IDs
            # Exclude test execution targets (which contain '::' or file extensions)
            raw_parents = list(relations.get(obj_id, set()) | relations.get(req_id, set()))
            parents = [
                obj_to_req_id.get(p, p)
                for p in raw_parents
                if "::" not in p and not p.endswith((".py", ".cpp", ".c", ".h", ".feature"))
            ]

            req = Requirement(
                id=str(req_id).strip(),
                revision=obj.attrib.get("LAST-CHANGE", "1.0"),
                title=title,
                description=cleaned_text,
                is_normative=is_normative,
                level=level,
                source_file=path.name,
                req_type=RequirementType.FUNCTIONAL,
                parent_ids=parents,
                attributes=attr_values,
            )
            requirements.append(req)

        return requirements

    def _extract_attribute_definitions(self, root: Element) -> Dict[str, str]:
        """Maps attribute definition IDENTIFIER to its user-facing LONG-NAME."""
        attr_defs: Dict[str, str] = {}
        for elem in root.iter():
            local_name = _strip_ns(elem.tag)
            if local_name.startswith("ATTRIBUTE-DEFINITION-"):
                ident = elem.attrib.get("IDENTIFIER")
                long_name = elem.attrib.get("LONG-NAME") or ident
                if ident and long_name:
                    attr_defs[ident] = long_name
        return attr_defs

    def _extract_relations(self, root: Element) -> Dict[str, Set[str]]:
        """Maps source (child) SPEC-OBJECT-REF to target (parent) SPEC-OBJECT-REFs."""
        relations: Dict[str, Set[str]] = {}
        for rel in self._find_all_by_local_name(root, "SPEC-RELATION"):
            source_ref = ""
            target_ref = ""
            for child in rel.iter():
                c_tag = _strip_ns(child.tag)
                if c_tag in {"SPEC-OBJECT-REF", "SOURCE-REF"}:
                    # Check parent tag to determine if source or target
                    if not source_ref and child.text:
                        source_ref = child.text.strip()
                elif c_tag == "TARGET-REF" and child.text:
                    target_ref = child.text.strip()

            # Some ReqIF schemas structure as <SOURCE><SPEC-OBJECT-REF>child</...></SOURCE>
            for src_wrapper in self._find_all_by_local_name(rel, "SOURCE"):
                for ref in self._find_all_by_local_name(src_wrapper, "SPEC-OBJECT-REF"):
                    if ref.text:
                        source_ref = ref.text.strip()
            for tgt_wrapper in self._find_all_by_local_name(rel, "TARGET"):
                for ref in self._find_all_by_local_name(tgt_wrapper, "SPEC-OBJECT-REF"):
                    if ref.text:
                        target_ref = ref.text.strip()

            if source_ref and target_ref:
                relations.setdefault(source_ref, set()).add(target_ref)

        return relations

    def _extract_object_attributes(
        self, spec_object: Element, attr_defs: Dict[str, str]
    ) -> Dict[str, str]:
        """Extracts key-value attributes for a SPEC-OBJECT."""
        attributes: Dict[str, str] = {}

        for val_elem in spec_object.iter():
            tag = _strip_ns(val_elem.tag)
            if not tag.startswith("ATTRIBUTE-VALUE-"):
                continue

            # Find definition reference
            def_ref = ""
            for child in val_elem.iter():
                child_tag = _strip_ns(child.tag)
                if child_tag.endswith("-REF") and child.text:
                    def_ref = child.text.strip()
                    break

            attr_name = attr_defs.get(def_ref, def_ref)

            # Find attribute value
            val_text = val_elem.attrib.get("THE-VALUE", "")
            if not val_text:
                # XHTML values are stored as inner XML nodes
                for the_val in self._find_all_by_local_name(val_elem, "THE-VALUE"):
                    # Serialize inner XML content
                    val_text = "".join(ET.tostring(c, encoding="unicode") for c in the_val) or (the_val.text or "")
                    break
                if not val_text and val_elem.text:
                    val_text = val_elem.text.strip()

            if attr_name and val_text:
                attributes[attr_name] = val_text.strip()

        return attributes

    def _find_all_by_local_name(self, element: Element, local_name: str) -> List[Element]:
        """Finds all child elements matching local tag name regardless of namespace."""
        matches: List[Element] = []
        for elem in element.iter():
            if _strip_ns(elem.tag) == local_name:
                matches.append(elem)
        return matches
