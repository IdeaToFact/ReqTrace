# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Requirement data models for ReqTrace.
Represents safety-critical requirements across multi-tier hierarchies.
"""

import hashlib
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, model_validator


class RequirementType(str, Enum):
    FUNCTIONAL = "functional"
    PERFORMANCE = "performance"
    SAFETY = "safety"
    INTERFACE = "interface"
    SECURITY = "security"


class RequirementLevel(str, Enum):
    SYSTEM = "system"
    HIGH_LEVEL = "high_level"       # HLR (High-Level Requirement)
    LOW_LEVEL = "low_level"         # LLR (Low-Level Requirement)
    ARCHITECTURE = "architecture"


class VerificationMethod(str, Enum):
    TEST = "test"                   # Verified via dynamic test execution (default)
    ANALYSIS = "analysis"           # Engineering calculation, simulation, modeling
    INSPECTION = "inspection"       # Visual inspection or physical measurement
    REVIEW = "review"               # Formal code/design walkthrough or checklist
    DEMONSTRATION = "demonstration" # Observable operational behavior/flight test


class Requirement(BaseModel):
    id: str
    revision: Optional[str] = "1.0"
    title: str
    description: str
    is_normative: bool = True       # True = "shall" requirement; False = informational/heading
    level: RequirementLevel = RequirementLevel.HIGH_LEVEL
    verification_method: VerificationMethod = VerificationMethod.TEST
    source_file: str
    source_offset: Optional[Tuple[int, int]] = None  # (start_char, end_char)
    req_type: RequirementType = RequirementType.FUNCTIONAL
    parent_ids: List[str] = Field(default_factory=list)  # Hierarchical allocation
    attributes: Dict[str, Any] = Field(default_factory=dict)
    sha256: str = ""

    @model_validator(mode="after")
    def compute_sha256(self) -> "Requirement":
        if not self.sha256:
            # Deterministic hash of normalized core attributes
            content = f"{self.id}|{self.title.strip()}|{self.description.strip()}|{self.level.value}|{self.is_normative}|{self.verification_method.value}"
            self.sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return self
