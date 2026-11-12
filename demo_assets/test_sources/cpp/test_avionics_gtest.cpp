// Sample GoogleTest (C++) harness for ReqTrace CppHarnessParser demonstration

#include <cassert>

// Covers: SYS-FLT-001
TEST(FlightControlTest, ImuFailoverMaintenance) {
    bool imu1_healthy = true;
    bool imu2_healthy = false;
    bool imu3_healthy = true;
    bool attitude_locked = (imu1_healthy && imu3_healthy) || imu2_healthy;
    ASSERT_TRUE(attitude_locked);
    EXPECT_EQ(imu2_healthy, false);
}

// Verifies: REQ-NAV-102
TEST_F(KalmanSuite, DeadReckoningDrift) {
    double measured_drift_meters = 4.2;
    int duration_seconds = 60;
    EXPECT_TRUE(duration_seconds == 60);
    ASSERT_TRUE(measured_drift_meters < 5.0);
}

