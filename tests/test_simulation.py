import unittest
from neo.simulation import NeoWorld


class TestNeoWorld(unittest.TestCase):
    
    def test_forward_path_rejects_wall_collision(self):
        world = NeoWorld()
        world.x = 160
        world.y = 110
        world.heading = 0

        self.assertFalse(world.forward_path_is_clear(1.0))

    def test_forward_path_accepts_clear_short_move(self):
        world = NeoWorld()
        world.x = 410
        world.y = 365
        world.heading = 0

        self.assertTrue(world.forward_path_is_clear(0.2))

    
    def test_turn_then_move_check_does_not_change_world(self):
        world = NeoWorld()
        original_pose = (world.x, world.y, world.heading)
        original_path = list(world.path)

        result = world.can_turn_then_move("TURN_LEFT")

        self.assertIsInstance(result, bool)
        self.assertEqual(
            (world.x, world.y, world.heading),
            original_pose,
        )
        self.assertEqual(world.path, original_path)

    def test_turn_then_move_rejects_invalid_direction(self):
        world = NeoWorld()

        self.assertFalse(world.can_turn_then_move("FORWARD"))

    def test_turn_then_move_rejects_invalid_duration(self):
        world = NeoWorld()

        self.assertFalse(
            world.can_turn_then_move(
                "TURN_LEFT",
                turn_duration=float("nan"),
            )
        )


if __name__ == "__main__":
    unittest.main()
