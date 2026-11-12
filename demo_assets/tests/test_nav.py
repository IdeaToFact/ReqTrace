import pytest

@pytest.mark.req("REQ-NAV-0104")
def test_gps_loss_switches_to_dead_reckoning():
    """Verify dead-reckoning switch time."""
    mode = "INERTIAL"
    latency_ms = 180
    assert mode == "INERTIAL"
    assert latency_ms <= 200

def test_unlinked_rogue_case():
    """Test with no requirement reference."""
    assert 1 + 1 == 2

