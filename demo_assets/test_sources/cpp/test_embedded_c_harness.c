/*
 * Sample embedded C custom macro test harness configured in reqtrace.toml
 * (`MY_FLIGHT_TEST`, `VERIFY_SIGNAL`, `CHECK_BOUNDS`).
 */

// Verifies: REQ-COM-301
MY_FLIGHT_TEST(ArincBus, OverloadShedding) {
    int bus_utilization_pct = 91;
    int dropped_non_critical_frames = 14;
    VERIFY_SIGNAL(bus_utilization_pct > 85);
    CHECK_BOUNDS(dropped_non_critical_frames > 0);
}

