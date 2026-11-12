# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Word (.docx) Specification Parser for ReqTrace.
Extracts requirements from structured tables and paragraph hierarchies in Word documents.
100% offline and deterministic using python-docx.
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import docx
from docx.table import Table as DocxTable

from reqtrace.models.requirement import Requirement, RequirementLevel, RequirementType


REQ_ID_PATTERN = re.compile(
    r"\b([A-Z][A-Z0-9]{1,9}(?:[-_][A-Z0-9]+)+)\b"
)
REQ_PREFIX_PATTERN = re.compile(
    r"^[\s\[\(\*]*([A-Z][A-Z0-9]{1,9}(?:[-_][A-Z0-9]+)+)[\s\]\)\:\-\*]+(.*)",
    re.DOTALL
)


class DocxSpecificationParser:
    """
    Parses Microsoft Word (.docx) specifications into canonical Requirement objects.
    Extracts requirements both from requirement tables and hierarchical tagged paragraphs.
    """

    def __init__(self, id_pattern: Optional[re.Pattern] = None) -> None:
        self.id_pattern = id_pattern or REQ_ID_PATTERN

    def parse(self, docx_path: Path) -> List[Requirement]:
        if not docx_path.exists():
            raise FileNotFoundError(f"DOCX specification not found: {docx_path}")

        doc = docx.Document(docx_path)
        requirements: List[Requirement] = []
        seen_ids: set = set()

        # 1. Parse tables for tabular requirements matrices
        for table_idx, table in enumerate(doc.tables):
            table_reqs = self._parse_table(table, docx_path, table_idx)
            for req in table_reqs:
                if req.id not in seen_ids:
                    requirements.append(req)
                    seen_ids.add(req.id)

        # 2. Parse paragraphs for heading-based and tagged inline requirements
        para_reqs = self._parse_paragraphs(doc.paragraphs, docx_path)
        for req in para_reqs:
            if req.id not in seen_ids:
                requirements.append(req)
                seen_ids.add(req.id)

        return requirements

    def _parse_table(self, table: DocxTable, docx_path: Path, table_idx: int) -> List[Requirement]:
        """Parse structured requirement tables."""
        if len(table.rows) < 2:
            return []

        # Find header indices
        header_cells = [cell.text.strip().lower() for cell in table.rows[0].cells]
        id_col = -1
        desc_col = -1
        title_col = -1
        level_col = -1
        type_col = -1

        for i, header in enumerate(header_cells):
            if any(term in header for term in ["req id", "requirement id", "req_id", "req-id", "id", "tag"]):
                if id_col == -1:
                    id_col = i
            elif any(term in header for term in ["text", "description", "specification", "statement", "shall"]):
                if desc_col == -1:
                    desc_col = i
            elif any(term in header for term in ["title", "name", "summary", "subject"]):
                if title_col == -1:
                    title_col = i
            elif any(term in header for term in ["level", "tier"]):
                if level_col == -1:
                    level_col = i
            elif any(term in header for term in ["type", "category"]):
                if type_col == -1:
                    type_col = i

        # If table doesn't have an ID and text column, skip table parsing
        if id_col == -1 or desc_col == -1:
            return []

        table_reqs: List[Requirement] = []
        for row_idx, row in enumerate(table.rows[1:], start=2):
            cells = row.cells
            if len(cells) <= max(id_col, desc_col):
                continue

            raw_id = cells[id_col].text.strip()
            # Match standard pattern or validate non-empty alphanumeric
            match = self.id_pattern.search(raw_id)
            if not match:
                continue
            req_id = match.group(1)

            raw_text = cells[desc_col].text.strip()
            raw_title = cells[title_col].text.strip() if title_col != -1 and title_col < len(cells) else ""
            if not raw_title:
                raw_title = f"Requirement {req_id}"

            # Level inference
            level = RequirementLevel.HIGH_LEVEL
            if level_col != -1 and level_col < len(cells):
                lvl_val = cells[level_col].text.strip().lower()
                if "sys" in lvl_val:
                    level = RequirementLevel.SYSTEM
                elif "low" in lvl_val or "llr" in lvl_val:
                    level = RequirementLevel.LOW_LEVEL
                elif "arch" in lvl_val:
                    level = RequirementLevel.ARCHITECTURE

            # Type inference
            req_type = RequirementType.FUNCTIONAL
            if type_col != -1 and type_col < len(cells):
                typ_val = cells[type_col].text.strip().lower()
                if "safety" in typ_val:
                    req_type = RequirementType.SAFETY
                elif "perf" in typ_val:
                    req_type = RequirementType.PERFORMANCE
                elif "sec" in typ_val:
                    req_type = RequirementType.SECURITY
                elif "int" in typ_val:
                    req_type = RequirementType.INTERFACE

            req = Requirement(
                id=req_id,
                title=raw_title,
                description=raw_text,
                level=level,
                req_type=req_type,
                source_file=str(docx_path).replace("\\", "/"),
                line_start=row_idx,
                line_end=row_idx,
                attributes={"table_index": table_idx, "row_index": row_idx},
            )
            table_reqs.append(req)

        return table_reqs

    def _parse_paragraphs(self, paragraphs, docx_path: Path) -> List[Requirement]:
        """Parse requirements declared in document paragraphs and heading hierarchies."""
        para_reqs: List[Requirement] = []
        current_section = ""
        current_parent_id: Optional[str] = None

        for p_idx, p in enumerate(paragraphs, start=1):
            text = p.text.strip()
            if not text:
                continue

            style_name = p.style.name.lower() if p.style else ""
            if "heading" in style_name:
                current_section = text
                # If heading itself has a requirement ID, track as potential parent
                match = self.id_pattern.search(text)
                if match:
                    current_parent_id = match.group(1)
                continue

            # Check for requirement prefix: e.g. "REQ-PWR-001: The system shall..."
            match = REQ_PREFIX_PATTERN.match(text)
            if match:
                req_id = match.group(1)
                req_text = match.group(2).strip()
                title = f"Requirement {req_id}"
                if current_section:
                    title = f"[{current_section}] {title}"

                parent_ids = [current_parent_id] if current_parent_id and current_parent_id != req_id else []

                req = Requirement(
                    id=req_id,
                    title=title,
                    description=req_text,
                    level=RequirementLevel.HIGH_LEVEL,
                    req_type=RequirementType.FUNCTIONAL,
                    source_file=str(docx_path).replace("\\", "/"),
                    line_start=p_idx,
                    line_end=p_idx,
                    parent_ids=parent_ids,
                    attributes={"section": current_section},
                )
                para_reqs.append(req)

        return para_reqs
