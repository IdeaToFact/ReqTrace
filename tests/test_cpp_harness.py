# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for CppHarnessParser.
Verifies parsing of MISRA C/C++ GoogleTest fixtures and custom macros.
"""

from pathlib import Path
from reqtrace.config import CppParserConfig
from reqtrace.parsers.code.cpp_harness import CppHarnessParser


SAMPLE_CPP_TEST = """
// Flight Control Navigation Test Suite
#include "gtest/gtest.h"
#include "navigation.h"

// Covers: REQ-NAV-0104
TEST(NavSuite, FailsafeSwitchTime) {
    NavComputer nav;
    nav.InjectGpsFault();
    ASSERT_EQ(nav.GetMode(), NavMode::INERTIAL);
    EXPECT_TRUE(nav.GetSwitchLatencyMs() <= 200);
}

/*
 * Requirements: REQ-PWR-002
 */
TEST_F(PowerFixture, BatteryDrainUnderLoad) {
    PowerBus bus;
    bus.SimulateMainGeneratorLoss();
    ASSERT_TRUE(bus.IsBatteryConnected());
    EXPECT_GE(bus.GetVoltage(), 24.0);
}

void HelperFunction() {
    // Non-test function
}
"""


def test_cpp_gtest_extraction(tmp_path: Path) -> None:
    test_file = tmp_path / "test_nav.cpp"
    test_file.write_text(SAMPLE_CPP_TEST, encoding="utf-8")

    parser = CppHarnessParser(
        CppParserConfig(
            test_macro_names=["TEST", "TEST_F"],
            assert_macro_names=["ASSERT_EQ", "EXPECT_TRUE", "ASSERT_TRUE", "EXPECT_GE"],
        )
    )
    artifacts = parser.parse_file(test_file)

    assert len(artifacts) == 2

    # Test 1: TEST(NavSuite, FailsafeSwitchTime)
    t1 = next(a for a in artifacts if "NavSuite.FailsafeSwitchTime" in a.id)
    assert t1.declared_req_refs == ["REQ-NAV-0104"]
    assert len(t1.assertion_statements) == 2
    assert "ASSERT_EQ(nav.GetMode(), NavMode::INERTIAL);" in t1.assertion_statements
    assert "EXPECT_TRUE(nav.GetSwitchLatencyMs() <= 200);" in t1.assertion_statements

    # Test 2: TEST_F(PowerFixture, BatteryDrainUnderLoad)
    t2 = next(a for a in artifacts if "PowerFixture.BatteryDrainUnderLoad" in a.id)
    assert t2.declared_req_refs == ["REQ-PWR-002"]
    assert len(t2.assertion_statements) == 2
    assert "ASSERT_TRUE(bus.IsBatteryConnected());" in t2.assertion_statements
    assert "EXPECT_GE(bus.GetVoltage(), 24.0);" in t2.assertion_statements

