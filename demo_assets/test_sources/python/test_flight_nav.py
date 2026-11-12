"""
Sample PyTest navigation suite demonstrating multiple explicit requirement linkage styles
plus an intentional rogue unlinked test for bidirectional gap auditing.
"""

import pytest


@pytest.mark.req("REQ-NAV-101")
def test_gps_loss_dead_reckoning():
    """Verify inertial dead-reckoning switchover stays under 200ms."""
    mode = "INERTIAL"
    switchover_ms = 145
    assert mode == "INERTIAL"
    assert switchover_ms <= 200


def test_triple_imu_voter_failover():
    """
    Validates triple-modular attitude voter resilience when IMU-2 fails.
    Covers SYS-FLT-001.
    """
    active_imus = ["IMU-1", "IMU-3"]
    attitude_valid = len(active_imus) >= 2
    assert attitude_valid is True
    assert len(active_imus) == 2


def test_kalman_drift_over_60s():
    # Covers: REQ-NAV-102
    position_drift_m = 3.4
    interval_sec = 60
    assert interval_sec == 60
    assert position_drift_m < 5.0


def test_diagnostic_uart_banner():
    """Intentional rogue test without any requirement linkage."""
    banner = "AVIONICS BOOT OK"
    assert banner.startswith("AVIONICS")

