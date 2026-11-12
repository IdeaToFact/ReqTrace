# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for ReqTrace configuration loading and validation.
"""

from pathlib import Path
from reqtrace.config import ReqTraceConfig, load_config


def test_load_default_config(tmp_path: Path) -> None:
    # Pointing to non-existent file returns default config
    cfg = load_config(tmp_path / "non_existent.toml")
    assert isinstance(cfg, ReqTraceConfig)
    assert cfg.project.standard == "DO-178C"
    assert cfg.thresholds.min_coverage_pct == 95.0
    assert cfg.thresholds.fail_on_orphans is True


def test_load_existing_reqtrace_toml() -> None:
    config_path = Path(__file__).parent.parent / "reqtrace.toml"
    assert config_path.exists()
    cfg = load_config(config_path)
    assert cfg.project.name == "FlightControl-VnV"
    assert cfg.reqif_mapping.id_attribute == "Customer_Req_Number"
    assert "ASSERT_EQ" in cfg.parsers.cpp.assert_macro_names

