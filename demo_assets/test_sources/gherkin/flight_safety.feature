@AVIONICS
Feature: Flight Navigation and Hydraulic Fail-Safe Verification
  As a flight test engineer
  I want deterministic behavioral scenarios mapped directly to safety requirements

  @REQ-NAV-101
  Scenario: Navigation failover on primary GPS signal loss
    Given the aircraft is cruising with valid GPS and INS lock
    When primary GPS reception drops for more than 10ms
    Then the navigation computer switches to inertial dead-reckoning within 200ms
    And pilot primary flight display reports INERTIAL mode

  @REQ-HYD-401 @SAFETY
  Scenario: Hydraulic servo bypass activation on pressure loss
    Given hydraulic loop A is operating at 3000 PSI
    When line pressure drops below 1800 PSI
    Then the servo controller engages the bypass valve within 50ms
    And actuator jam fault flag stays cleared

