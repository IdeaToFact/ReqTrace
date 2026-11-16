# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Requirements Traceability Matrix (RTM) and Gap Analysis models.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from reqtrace.models.requirement import Requirement
from reqtrace.models.test_artifact import TestArtifact
from reqtrace.models.trace_link import TraceLink


class GapAnalysisResult(BaseModel):
    total_requirements: int = 0
    normative_requirements: int = 0
    covered_requirements: int = 0
    orphan_requirements: List[str] = Field(default_factory=list)
    total_tests: int = 0
    unlinked_tests: List[str] = Field(default_factory=list)
    failed_tests: List[str] = Field(default_factory=list)
    stale_links: List[str] = Field(default_factory=list)
    coverage_percentage: float = 0.0
    is_passing: bool = False
    gating_errors: List[str] = Field(default_factory=list)


class RequirementsTraceabilityMatrix(BaseModel):
    project_name: str
    project_version: str = "1.0.0"
    standard: str = "DO-178C"
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    requirements: Dict[str, Requirement] = Field(default_factory=dict)
    test_artifacts: Dict[str, TestArtifact] = Field(default_factory=dict)
    trace_links: List[TraceLink] = Field(default_factory=list)
    gap_analysis: Optional[GapAnalysisResult] = None
    merkle_root: str = ""

