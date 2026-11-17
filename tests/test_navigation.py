
"""Automated tests for Neo's directional navigation."""

import unittest

from neo.decision import RobotInputs
from neo.navigation import NeoNavigation


class TestNeoNavigation(unittest.TestCase):

    def setUp(self):
        self.nav = NeoNavigation()

    def update(
        self,
        t,
        front,
        left=100,
        right=100,
        emergency=False,
        navigate=True,
        touch=False,
    ):
        return self.nav.update(
            now=t,
            inputs=RobotInputs(
                obstacle_distance_cm=front,
                touch=touch,
                emergency_stop=emergency,
                left_distance_cm=left,
                right_distance_cm=right,
            ),
            navigation_requested=navigate,
        )

    def test_clear_path_starts_moving(self):
        action = self.update(0.0, 100)
        self.assertEqual(action.command, "FORWARD")
        self.assertEqual(self.nav.state, self.nav.MOVING)

    def test_obstacle_stops_robot(self):
        self.update(0.0, 100)
        action = self.update(0.2, 10)
        self.assertEqual(action.command, "STOP")
        self.assertEqual(self.nav.state, self.nav.BLOCKED)

    def test_missing_front_sensor_stops_robot(self):
        self.update(0.0, 100)
        action = self.update(0.2, None)
        self.assertEqual(action.command, "STOP")
        self.assertEqual(self.nav.state, self.nav.IDLE)

    def test_emergency_stop_is_latched(self):
        action = self.update(0.0, 100, emergency=True)
        self.assertEqual(action.command, "STOP")
        self.assertEqual(self.nav.state, self.nav.EMERGENCY_STOP)

        action = self.update(1.0, 100)
        self.assertEqual(action.command, "STOP")
        self.assertEqual(self.nav.state, self.nav.EMERGENCY_STOP)

    def test_emergency_reset_allows_navigation(self):
        self.update(0.0, 100, emergency=True)
        self.nav.reset_emergency_stop()
        action = self.update(1.0, 100)
        self.assertEqual(action.command, "FORWARD")

    def test_navigation_disabled_stops(self):
        self.update(0.0, 100)
        action = self.update(0.2, 100, navigate=False)
        self.assertEqual(action.command, "STOP")
        self.assertEqual(self.nav.state, self.nav.IDLE)

    def test_negative_front_distance_is_invalid(self):
        action = self.update(0.0, -1)
        self.assertEqual(action.command, "STOP")

    def test_touch_pauses_navigation(self):
        self.update(0.0, 100)
        action = self.update(0.2, 100, touch=True)
        self.assertEqual(action.command, "STOP")
        self.assertEqual(self.nav.state, self.nav.IDLE)

    def test_turn_toward_side_with_more_clearance(self):
        self.update(0.0, 100)
        self.update(0.2, 10, left=60, right=40)
        action = self.update(0.8, 10, left=60, right=40)
        self.assertEqual(action.command, "TURN_LEFT")
        self.assertEqual(self.nav.state, self.nav.TURNING)

    def test_turn_right_when_right_has_more_clearance(self):
        self.update(0.0, 100)
        self.update(0.2, 10, left=35, right=80)
        action = self.update(0.8, 10, left=35, right=80)
        self.assertEqual(action.command, "TURN_RIGHT")

    def test_blocked_left_chooses_right(self):
        self.update(0.0, 100)
        self.update(0.2, 10, left=10, right=60)
        action = self.update(0.8, 10, left=10, right=60)
        self.assertEqual(action.command, "TURN_RIGHT")

    def test_blocked_right_chooses_left(self):
        self.update(0.0, 100)
        self.update(0.2, 10, left=60, right=10)
        action = self.update(0.8, 10, left=60, right=10)
        self.assertEqual(action.command, "TURN_LEFT")

    def test_both_sides_blocked_never_turns(self):
        self.update(0.0, 100)
        self.update(0.2, 10, left=10, right=15)
        action = self.update(0.8, 10, left=10, right=15)
        self.assertEqual(action.command, "STOP")
        self.assertEqual(self.nav.state, self.nav.BLOCKED)

    def test_missing_side_reading_never_turns(self):
        self.update(0.0, 100)
        self.update(0.2, 10, left=None, right=60)
        action = self.update(0.8, 10, left=None, right=60)
        self.assertEqual(action.command, "STOP")
        self.assertEqual(self.nav.state, self.nav.BLOCKED)

    def test_invalid_side_reading_never_turns(self):
        self.update(0.0, 100)
        self.update(0.2, 10, left=-1, right=60)
        action = self.update(0.8, 10, left=-1, right=60)
        self.assertEqual(action.command, "STOP")

    def test_resume_only_after_front_clears(self):
        self.update(0.0, 100)
        self.update(0.2, 10, left=60, right=40)
        self.update(0.8, 10, left=60, right=40)  # Begin left turn.
        action = self.update(1.5, 10, left=60, right=40)
        self.assertEqual(action.command, "STOP")
        self.assertEqual(self.nav.state, self.nav.BLOCKED)

        # Left was attempted; alternate safe direction is right.
        action = self.update(2.1, 10, left=60, right=40)
        self.assertEqual(action.command, "TURN_RIGHT")

        # Turn completes, but front still blocked.
        action = self.update(2.8, 10, left=60, right=40)
        self.assertEqual(action.command, "STOP")

        # Both directions have been attempted; no repeated blind turns.
        action = self.update(3.4, 10, left=60, right=40)
        self.assertEqual(action.command, "STOP")

        # A fresh clear front reading allows recovery.
        action = self.update(3.5, 100, left=60, right=40)
        self.assertEqual(action.command, "FORWARD")
        self.assertEqual(self.nav.state, self.nav.MOVING)

    
    def test_collision_after_recovery_turn_avoids_failed_turn(self):
        # Neo starts moving, then encounters an obstacle.
        self.update(0.0, 100)
        self.update(0.2, 10, left=80, right=60)

        # Wait for the blocked pause and start turning left.
        action = self.update(0.8, 10, left=80, right=60)
        self.assertEqual(action.command, "TURN_LEFT")

        # Turn completes and the controller resumes forward movement.
        action = self.update(1.5, 100, left=80, right=60)
        self.assertEqual(action.command, "FORWARD")

        # The simulation reports a collision during that forward move.
        action = self.nav.update(
            now=1.6,
            inputs=RobotInputs(
                obstacle_distance_cm=10,
                touch=False,
                emergency_stop=False,
                left_distance_cm=80,
                right_distance_cm=60,
            ),
            navigation_requested=True,
            collision_detected=True,
        )
        self.assertEqual(action.command, "STOP")

        # After the pause, Neo must choose the alternate direction.
        action = self.update(2.2, 10, left=80, right=60)
        self.assertEqual(action.command, "TURN_RIGHT")

if __name__ == "__main__":
    unittest.main(verbosity=2)