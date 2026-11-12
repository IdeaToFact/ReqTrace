# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Workspace Manifest and Project Metadata Models for ReqTrace.
Provides file abstraction, metadata tracking, and recent workspace persistence.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class WorkspaceManifest(BaseModel):
    """
    Abstraction layer decoupling storage filenames and formats from application logic.
    Stored at .reqtrace/workspace.json.
    """
    schema_version: str = "1.0"
    project_file: str = ".reqtrace/project.json"
    requirements_file: str = "requirements.json"
    tests_file: str = "tests.json"
    reviews_file: str = ".reqtrace/reviews.jsonl"
    baselines_dir: str = ".reqtrace/baselines"


class ProjectMetadata(BaseModel):
    """
    Formal engineering metadata bound to the verification session.
    Stored at .reqtrace/project.json.
    """
    schema_version: str = "1.0"
    project_name: str
    project_id: Optional[str] = None
    target_standard: Optional[str] = "DO-178C DAL B"
    spec_version: Optional[str] = "1.0"
    baseline_id: Optional[str] = "BASELINE-001"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_analysis: Optional[str] = None
    settings: Dict[str, Any] = Field(default_factory=lambda: {
        "strict_hash_binding": True,
        "allow_heuristic_linking": True,
        "min_confidence_threshold": 0.80,
    })


class WorkspaceInfo(BaseModel):
    """
    Record in the global recent workspaces registry (~/.reqtrace/workspaces.json).
    """
    path: str
    name: str
    last_opened: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    target_standard: Optional[str] = None
    baseline_id: Optional[str] = None

