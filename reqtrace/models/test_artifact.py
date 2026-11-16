# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Test artifact models for ReqTrace.
Represents test suites, test cases, and their execution verdicts.
"""

import hashlib
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class TestVerdict(str, Enum):
    __test__ = False
    UNEXECUTED = "unexecuted"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


# Backward compatibility alias
TestExecutionStatus = TestVerdict


class TestArtifact(BaseModel):
    __test__ = False
    id: str                          # e.g., "tests/test_nav.py::test_gps_loss"
    file_path: str
    line_start: int
    line_end: int
    framework: str                   # "pytest", "gtest", "gherkin"
    declared_req_refs: List[str] = Field(default_factory=list)
    assertion_statements: List[str] = Field(default_factory=list)
    execution_status: TestVerdict = TestVerdict.UNEXECUTED
    execution_time_sec: Optional[float] = None
    junit_source: Optional[str] = None
    junit_timestamp: Optional[str] = None
    source_sha256_at_scan: str = ""
    source_mtime_at_scan: float = 0.0
    sha256: str = ""

    @property
    def has_assertions(self) -> bool:
        return len(self.assertion_statements) > 0

    @model_validator(mode="after")
    def compute_sha256(self) -> "TestArtifact":
        if not self.sha256:
            assertions = ";".join(self.assertion_statements)
            refs = ";".join(sorted(self.declared_req_refs))
            content = f"{self.id}|{self.file_path}|{self.line_start}:{self.line_end}|{refs}|{assertions}"
            self.sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return self
