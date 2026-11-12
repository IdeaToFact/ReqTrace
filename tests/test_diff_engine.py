# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for SpecDiffEngine and Requirement Revision Drift.
"""

from reqtrace.analysis.diff_engine import SpecDiffEngine
from reqtrace.models.requirement import Requirement, RequirementLevel


def test_spec_diff_engine_detects_all_categories() -> None:
    # Baseline v1
    v1_unchanged = Requirement(id="REQ-01", title="Title 1", description="Text 1", source_file="v1.reqif")
    v1_modified = Requirement(id="REQ-02", title="Title 2", description="Latency 200ms", source_file="v1.reqif")
    v1_removed = Requirement(id="REQ-03", title="Old Feature", description="Legacy subsystem", source_file="v1.reqif")

    # Revision v2
    v2_unchanged = Requirement(id="REQ-01", title="Title 1", description="Text 1", source_file="v2.reqif")
    # Parameter tightened to 100ms
    v2_modified = Requirement(id="REQ-02", title="Title 2", description="Latency 100ms", level=RequirementLevel.LOW_LEVEL, source_file="v2.reqif")
    v2_added = Requirement(id="REQ-04", title="New Cyber Feature", description="Encryption check", source_file="v2.reqif")

    engine = SpecDiffEngine()
    result = engine.compare(
        old_reqs=[v1_unchanged, v1_modified, v1_removed],
        new_reqs=[v2_unchanged, v2_modified, v2_added],
        old_name="v1.reqif",
        new_name="v2.reqif",
    )

    assert result.unchanged_count == 1
    assert len(result.added) == 1
    assert result.added[0].id == "REQ-04"

    assert len(result.removed) == 1
    assert result.removed[0].id == "REQ-03"

    assert len(result.modified) == 1
    assert result.modified[0].req_id == "REQ-02"
    assert "description modified" in result.modified[0].changes

    # Stale requirements must include both REQ-02 (modified) and REQ-03 (removed)
    assert set(result.stale_req_ids) == {"REQ-02", "REQ-03"}

