# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Export Request and Result Models for ReqTrace Export Service.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ExportFormat(str, Enum):
    CSV = "csv"
    REQIF = "reqif"
    HTML = "html"
    JSON = "json"


class ExportRequest(BaseModel):
    """
    Typed request payload for unified deliverable generation.
    """
    format: ExportFormat = ExportFormat.CSV
    include_reviews: bool = True
    include_unlinked: bool = True
    baseline_tag: Optional[str] = None


class ExportResult(BaseModel):
    """
    Deterministic result payload describing the generated export artifact.
    """
    export_id: str
    format: ExportFormat
    filename: str
    file_path: str
    size_bytes: int
    sha256: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

