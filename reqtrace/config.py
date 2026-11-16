# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Configuration module for ReqTrace.
Loads and validates reqtrace.toml configuration files.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


class ProjectConfig(BaseModel):
    name: str = "Default-Project"
    version: str = "1.0.0"
    standard: str = "DO-178C"


class ReqIFMappingConfig(BaseModel):
    id_attribute: str = "Customer_Req_Number"
    text_attribute: str = "ReqIF.Text"
    type_attribute: str = "Object Type"
    normative_value: str = "Requirement"
    level_attribute: str = "Requirement Level"


class SanitizerConfig(BaseModel):
    strip_xhtml: bool = True
    normalize_whitespace: bool = True


class CppParserConfig(BaseModel):
    test_macro_names: List[str] = Field(
        default_factory=lambda: ["TEST", "TEST_F", "MY_FLIGHT_TEST", "VERIFY_BLOCK"]
    )
    assert_macro_names: List[str] = Field(
        default_factory=lambda: [
            "ASSERT_EQ",
            "ASSERT_TRUE",
            "ASSERT_FALSE",
            "EXPECT_EQ",
            "EXPECT_TRUE",
            "EXPECT_FALSE",
            "VERIFY_SIGNAL",
            "CHECK_BOUNDS",
        ]
    )


class ParsersConfig(BaseModel):
    sanitizer: SanitizerConfig = Field(default_factory=SanitizerConfig)
    cpp: CppParserConfig = Field(default_factory=CppParserConfig)


class ExecutionConfig(BaseModel):
    reports: List[str] = Field(
        default_factory=lambda: ["test-results/junit.xml", "build/test-reports/*.xml"]
    )


class ModelsConfig(BaseModel):
    cache_dir: str = ".reqtrace/models"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    offline_fallback_deterministic: bool = True


class ThresholdsConfig(BaseModel):
    min_coverage_pct: float = 95.0
    coverage_basis: str = "linked_passing"  # "linked_passing" (engineering pass) or "verified" (audit sign-off)
    fail_on_orphans: bool = True
    fail_on_test_failures: bool = True
    fail_on_stale_reviews: bool = True
    high_confidence_threshold: float = 0.85
    medium_confidence_threshold: float = 0.60


class ReqTraceConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    reqif: Dict[str, ReqIFMappingConfig] = Field(
        default_factory=lambda: {"mapping": ReqIFMappingConfig()}
    )
    parsers: ParsersConfig = Field(default_factory=ParsersConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)

    @property
    def reqif_mapping(self) -> ReqIFMappingConfig:
        return self.reqif.get("mapping", ReqIFMappingConfig())


def load_config(config_path: Optional[Path | str] = None) -> ReqTraceConfig:
    """
    Loads ReqTrace configuration from toml file.
    If path is None, looks for reqtrace.toml in the current working directory.
    If not found, returns default configuration.
    """
    path = Path(config_path) if config_path else Path("reqtrace.toml")
    if not path.exists():
        return ReqTraceConfig()

    with open(path, "rb") as f:
        data = tomllib.load(f)

    return ReqTraceConfig.model_validate(data)

