# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
CSV and Delimited Tabular Requirements Matrix Parser.
Ingests requirements spreadsheets exported from Excel, Jira, or custom ALMs.
"""

import csv
from pathlib import Path
from typing import Dict, List, Optional
from reqtrace.models.requirement import (
    Requirement,
    RequirementLevel,
    RequirementType,
)


class CSVParser:
    def __init__(self, delimiter: Optional[str] = None) -> None:
        self.delimiter = delimiter

    def parse(self, file_path: Path | str) -> List[Requirement]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")

        # Detect dialect / delimiter if not specified
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            first_chunk = f.read(4096)
            delimiter = self.delimiter
            if not delimiter:
                if "\t" in first_chunk and "," not in first_chunk:
                    delimiter = "\t"
                elif ";" in first_chunk and "," not in first_chunk:
                    delimiter = ";"
                else:
                    delimiter = ","

            f.seek(0)
            reader = csv.DictReader(f, delimiter=delimiter)
            if not reader.fieldnames:
                return []

            field_map = self._resolve_field_map(reader.fieldnames)
            requirements: List[Requirement] = []

            for row in reader:
                req_id_raw = self._get_value(row, field_map.get("id"))
                if not req_id_raw:
                    continue

                req_id = req_id_raw.strip()
                title = self._get_value(row, field_map.get("title")) or req_id
                description = self._get_value(row, field_map.get("description")) or title

                # Determine level
                level_raw = self._get_value(row, field_map.get("level")).lower()
                level = RequirementLevel.HIGH_LEVEL
                if "system" in level_raw:
                    level = RequirementLevel.SYSTEM
                elif "low" in level_raw or "llr" in level_raw:
                    level = RequirementLevel.LOW_LEVEL
                elif "arch" in level_raw:
                    level = RequirementLevel.ARCHITECTURE

                # Determine parent IDs
                parent_raw = self._get_value(row, field_map.get("parents"))
                parents: List[str] = []
                if parent_raw:
                    # Split on comma or semicolon
                    parts = [p.strip() for p in parent_raw.replace(";", ",").split(",")]
                    parents = [p for p in parts if p]

                # Determine normative
                norm_raw = self._get_value(row, field_map.get("normative")).lower()
                is_normative = True
                if norm_raw in {"false", "0", "no", "info", "heading", "non-normative"}:
                    is_normative = False

                req = Requirement(
                    id=req_id,
                    revision=self._get_value(row, field_map.get("revision")) or "1.0",
                    title=title.strip(),
                    description=description.strip(),
                    is_normative=is_normative,
                    level=level,
                    source_file=path.name,
                    req_type=RequirementType.FUNCTIONAL,
                    parent_ids=parents,
                    attributes={k: v for k, v in row.items() if v},
                )
                requirements.append(req)

        return requirements

    def _resolve_field_map(self, headers: List[str]) -> Dict[str, str]:
        """Maps canonical field names to actual CSV column headers (case-insensitive)."""
        lower_headers = {h.strip().lower(): h for h in headers}

        def find_match(candidates: List[str]) -> Optional[str]:
            for c in candidates:
                if c.lower() in lower_headers:
                    return lower_headers[c.lower()]
            return None

        return {
            "id": find_match(["id", "req_id", "requirement_id", "key", "number", "req id"]) or headers[0],
            "title": find_match(["title", "name", "summary", "short_desc", "req title"]),
            "description": find_match(["description", "text", "statement", "req_text", "detail", "specification"]),
            "level": find_match(["level", "tier", "hierarchy", "type", "req level"]),
            "parents": find_match(["parent", "parent_id", "parents", "parent_ids", "allocates_to", "traces_to", "allocated_from"]),
            "normative": find_match(["normative", "is_normative", "category", "normative?"]),
            "revision": find_match(["revision", "rev", "version", "version_id"]),
        }

    def _get_value(self, row: Dict[str, str], col_name: Optional[str]) -> str:
        if not col_name or col_name not in row or not row[col_name]:
            return ""
        return row[col_name].strip()

