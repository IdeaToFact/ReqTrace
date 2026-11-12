# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for GherkinFeatureParser.
"""

from pathlib import Path
from reqtrace.parsers.code.gherkin import GherkinFeatureParser


SAMPLE_FEATURE = """
@FEATURE_NAV @DO-178C
Feature: Aircraft Navigation & GPS Loss Failover

  Background:
    Given navigation computer is initialized

  @REQ-NAV-001 @CRITICAL
  Scenario: GPS Signal Acquisition Timeout
    Given the GPS receiver antenna is locked
    When the system queries time-to-first-fix
    Then the navigation computer shall register a valid 3D fix within 2.5 seconds
    And the GPS health status indicator shall be ACTIVE

  @REQ-NAV-002
  Scenario: Inertial Guidance Transition
    Given a primary GPS signal loss occurs
    When 50 milliseconds elapse without satellite lock
    Then the navigation computer shall switch to inertial guidance
    And issue a caution alert to the cockpit MFD
"""


def test_gherkin_feature_parsing(tmp_path: Path):
    feature_file = tmp_path / "nav.feature"
    feature_file.write_text(SAMPLE_FEATURE, encoding="utf-8")

    parser = GherkinFeatureParser()
    artifacts = parser.parse_file(feature_file)

    assert len(artifacts) == 2

    # Scenario 1
    scen1 = artifacts[0]
    assert "GPS Signal Acquisition Timeout" in scen1.id
    assert "REQ-NAV-001" in scen1.declared_req_refs
    assert "REQ-NAV-002" not in scen1.declared_req_refs
    assert "FEATURE_NAV" in scen1.declared_req_refs
    assert len(scen1.assertion_statements) == 2
    assert "valid 3D fix within 2.5 seconds" in scen1.assertion_statements[0]
    assert "GPS health status" in scen1.assertion_statements[1]
    assert scen1.framework == "gherkin"

    # Scenario 2
    scen2 = artifacts[1]
    assert "Inertial Guidance Transition" in scen2.id
    assert "REQ-NAV-002" in scen2.declared_req_refs
    assert "REQ-NAV-001" not in scen2.declared_req_refs
    assert len(scen2.assertion_statements) == 2
    assert "switch to inertial guidance" in scen2.assertion_statements[0]
