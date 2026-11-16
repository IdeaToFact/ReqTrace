# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for PythonASTParser.
"""

from pathlib import Path
from reqtrace.parsers.code.python_ast import PythonASTParser


SAMPLE_TEST_CODE = '''"""Sample avionics navigation tests."""
import pytest

@pytest.mark.req("REQ-NAV-0104")
def test_gps_loss_switches_to_dead_reckoning():
    """Verifies failsafe inertial navigation."""
    nav = MockNavSystem()
    nav.simulate_gps_loss()
    assert nav.mode == "INERTIAL"
    assert nav.switch_latency_ms <= 200

def test_sensor_voltage():
    # Covers: REQ-PWR-001
    sensor = MockSensor()
    assert sensor.voltage >= 26.0
    assert sensor.voltage <= 30.0

def helper_function():
    return True
'''


def test_python_ast_extraction(tmp_path: Path) -> None:
    test_file = tmp_path / "test_nav.py"
    test_file.write_text(SAMPLE_TEST_CODE, encoding="utf-8")

    parser = PythonASTParser()
    artifacts = parser.parse_file(test_file)

    # helper_function must NOT be extracted
    assert len(artifacts) == 2

    # Test 1: @pytest.mark.req
    t1 = next(a for a in artifacts if "test_gps_loss" in a.id)
    assert t1.declared_req_refs == ["REQ-NAV-0104"]
    assert len(t1.assertion_statements) == 2
    assert "assert nav.mode == 'INERTIAL'" in t1.assertion_statements
    assert "assert nav.switch_latency_ms <= 200" in t1.assertion_statements
    assert t1.line_start == 5
    assert t1.line_end == 10

    # Test 2: # Covers: REQ-PWR-001
    t2 = next(a for a in artifacts if "test_sensor_voltage" in a.id)
    assert t2.declared_req_refs == ["REQ-PWR-001"]
    assert len(t2.assertion_statements) == 2
    assert "assert sensor.voltage >= 26.0" in t2.assertion_statements
