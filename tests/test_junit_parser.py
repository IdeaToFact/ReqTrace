# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for JUnitParser.
"""

from pathlib import Path
from reqtrace.models.test_artifact import TestArtifact, TestExecutionStatus
from reqtrace.parsers.junit_parser import JUnitParser


SAMPLE_JUNIT_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="3" errors="0" failures="1" skipped="1" time="0.145">
    <testcase classname="tests.test_nav" name="test_gps_loss_switches_to_dead_reckoning" time="0.042"/>
    <testcase classname="tests.test_pwr" name="test_battery_low" time="0.035">
      <failure message="AssertionError: assert battery.level >= 20.0">Traceback...</failure>
    </testcase>
    <testcase classname="tests.test_pwr" name="test_solar_charging" time="0.001">
      <skipped message="Hardware simulator not connected"/>
    </testcase>
  </testsuite>
</testsuites>
"""


def test_junit_parsing_and_attachment(tmp_path: Path) -> None:
    junit_file = tmp_path / "junit.xml"
    junit_file.write_text(SAMPLE_JUNIT_XML, encoding="utf-8")

    parser = JUnitParser()
    results = parser.parse(junit_file)

    assert len(results) >= 3

    # Check parsed results
    r_pass = results["test_gps_loss_switches_to_dead_reckoning"]
    assert r_pass.status == TestExecutionStatus.PASSED
    assert r_pass.time_sec == 0.042

    r_fail = results["test_battery_low"]
    assert r_fail.status == TestExecutionStatus.FAILED
    assert "AssertionError" in (r_fail.failure_message or "")

    r_skip = results["test_solar_charging"]
    assert r_skip.status == TestExecutionStatus.SKIPPED

    # Attach to artifacts
    artifacts = [
        TestArtifact(
            id="test_nav.py::test_gps_loss_switches_to_dead_reckoning",
            file_path="tests/test_nav.py",
            line_start=1,
            line_end=10,
            framework="pytest",
        ),
        TestArtifact(
            id="test_pwr.py::test_battery_low",
            file_path="tests/test_pwr.py",
            line_start=1,
            line_end=10,
            framework="pytest",
        ),
        TestArtifact(
            id="test_pwr.py::test_solar_charging",
            file_path="tests/test_pwr.py",
            line_start=1,
            line_end=10,
            framework="pytest",
        ),
    ]

    updated = parser.attach_verdicts(artifacts, junit_file)
    assert updated[0].execution_status == TestExecutionStatus.PASSED
    assert updated[1].execution_status == TestExecutionStatus.FAILED
    assert updated[2].execution_status == TestExecutionStatus.SKIPPED

