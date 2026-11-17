
import unittest

from neo.robot_runtime import NeoRobotRuntime


class FakePersonality:
    """Test double that never touches Neo's persistent memory."""

    def __init__(self):
        self.mood = "happy"
        self.affection = 50
        self.pet_calls = 0
        self.update_calls = []

    def pet(self, now):
        self.pet_calls += 1

    def update(self, now, dt):
        self.update_calls.append((now, dt))


class TestNeoRobotRuntime(unittest.TestCase):

    def setUp(self):
        self.personality = FakePersonality()
        self.runtime = NeoRobotRuntime(personality=self.personality)

    def tick(self, now=0.0, **kwargs):
        defaults = {
            "obstacle_distance_cm": 100,
            "left_distance_cm": 50,
            "right_distance_cm": 50,
            "navigation_requested": True,
        }
        defaults.update(kwargs)
        return self.runtime.tick(now=now, **defaults)

    def test_clear_path_allows_forward_movement(self):
        status = self.tick()
        self.assertEqual(status.command, "FORWARD")
        self.assertEqual(status.navigation_state, "MOVING")

    def test_missing_front_sensor_stops_robot(self):
        status = self.tick(obstacle_distance_cm=None)
        self.assertEqual(status.command, "STOP")

    def test_nearby_obstacle_stops_robot(self):
        status = self.tick(obstacle_distance_cm=10)
        self.assertEqual(status.command, "STOP")

    def test_navigation_disabled_stops_robot(self):
        status = self.tick(navigation_requested=False)
        self.assertEqual(status.command, "STOP")

    def test_touch_pauses_robot(self):
        status = self.tick(touch=True)
        self.assertEqual(status.command, "STOP")

    def test_emergency_stop_latches(self):
        first = self.tick(emergency_stop=True)
        second = self.tick(now=1.0, emergency_stop=False)

        self.assertEqual(first.command, "STOP")
        self.assertEqual(first.navigation_state, "EMERGENCY_STOP")
        self.assertEqual(second.command, "STOP")
        self.assertEqual(second.navigation_state, "EMERGENCY_STOP")

    def test_emergency_reset_allows_movement(self):
        self.tick(emergency_stop=True)
        self.runtime.reset_emergency_stop()

        status = self.tick(now=1.0)
        self.assertEqual(status.command, "FORWARD")
        self.assertEqual(status.navigation_state, "MOVING")

    def test_personality_status_is_exposed(self):
        status = self.tick()
        self.assertEqual(status.mood, "happy")
        self.assertEqual(status.affection, 50)

    def test_pet_interaction_reaches_personality(self):
        self.tick(pet_interaction=True)
        self.assertEqual(self.personality.pet_calls, 1)

    def test_personality_update_receives_elapsed_time(self):
        self.tick(now=2.0)
        self.tick(now=5.0)

        self.assertEqual(
            self.personality.update_calls,
            [(2.0, 0.0), (5.0, 3.0)],
        )

    def test_time_cannot_move_backwards(self):
        self.tick(now=5.0)

        with self.assertRaises(ValueError):
            self.tick(now=4.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
