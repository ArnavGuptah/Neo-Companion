
"""Directional obstacle avoidance for Basic Mobile Neo.

Simulation only. This module does not control physical motors.
"""

import math

from neo.decision import RobotAction, RobotInputs


class NeoNavigation:
    OBSTACLE_DISTANCE_CM = 20.0
    SIDE_CLEARANCE_CM = 25.0
    TURN_DURATION_SECONDS = 0.6
    BLOCKED_PAUSE_SECONDS = 0.5

    IDLE = "IDLE"
    MOVING = "MOVING"
    BLOCKED = "BLOCKED"
    TURNING = "TURNING"
    EMERGENCY_STOP = "EMERGENCY_STOP"

    def __init__(self):
        self.state = self.IDLE
        self.turn_direction = "TURN_LEFT"
        self._state_started_at = 0.0
        self._attempted_turns = set()
        self._emergency_latched = False
        self._side_avoidance_requested = False
        self._side_turn_suppressed = False
        self._collision_recovery = False
        self._last_recovery_turn = None

    @staticmethod
    def _valid_distance(value):
        return (
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(value)
            and value >= 0
        )

    def reset_emergency_stop(self):
        """Clear the emergency latch explicitly."""
        self._emergency_latched = False
        self.state = self.IDLE
        self._attempted_turns.clear()
        self._side_avoidance_requested = False
        self._side_turn_suppressed = False
        self._collision_recovery = False
        self._last_recovery_turn = None

    def _begin_blocked(self, now, side_avoidance=False):
        self.state = self.BLOCKED
        self._state_started_at = now
        self._attempted_turns.clear()
        self._side_avoidance_requested = side_avoidance

    
    
    def _choose_turn(
        self,
        inputs,
        left_turn_safe=None,
        right_turn_safe=None,
    ):
        """Choose a sensor-clear direction that passes geometry checks."""

        left = inputs.left_distance_cm
        right = inputs.right_distance_cm

        if not self._valid_distance(left):
            return None
        if not self._valid_distance(right):
            return None

        candidates = []

        left_allowed = (
            left >= self.SIDE_CLEARANCE_CM
            and "TURN_LEFT" not in self._attempted_turns
            and left_turn_safe is not False
        )
        right_allowed = (
            right >= self.SIDE_CLEARANCE_CM
            and "TURN_RIGHT" not in self._attempted_turns
            and right_turn_safe is not False
        )

        if left_allowed:
            candidates.append(("TURN_LEFT", left))
        if right_allowed:
            candidates.append(("TURN_RIGHT", right))

        if not candidates:
            return None

        # Prefer the side with more measured clearance; ties prefer left.
        candidates.sort(
            key=lambda candidate: (
                candidate[1],
                candidate[0] == "TURN_LEFT",
            ),
            reverse=True,
        )
        return candidates[0][0]


    def update(
        self,
        now: float,
        inputs: RobotInputs,
        navigation_requested: bool = True,
        collision_detected: bool = False,
        path_blocked: bool = False,
        left_turn_safe=None,
        right_turn_safe=None,
    ) -> RobotAction:
        """Process one simulated navigation step."""

        if not self._valid_distance(now):
            return self._action("STOP", "Invalid simulation time", 90)

        if inputs.emergency_stop:
            self._emergency_latched = True

        if self._emergency_latched:
            self.state = self.EMERGENCY_STOP
            return self._action("STOP", "Emergency stop is latched", 100)

        if collision_detected:
            self.state = self.BLOCKED
            self._state_started_at = now
            self._collision_recovery = True

            # Don't immediately retry the direction that led to collision.
            if self._last_recovery_turn in ("TURN_LEFT", "TURN_RIGHT"):
                self._attempted_turns.add(self._last_recovery_turn)

            return self._action(
                "STOP",
                "Collision feedback received; avoiding the failed turn "
                "and reassessing the path",
                90,
            )

        if path_blocked and not collision_detected:
            self.state = self.BLOCKED
            self._state_started_at = now
            self._collision_recovery = True

            return self._action(
                "STOP",
                "Predictive guard blocked forward movement; "
                "stopping to reassess the path",
                85,
            )

        front = inputs.obstacle_distance_cm
        left = inputs.left_distance_cm
        right = inputs.right_distance_cm

        if not self._valid_distance(front):
            self.state = self.IDLE
            self._attempted_turns.clear()
            return self._action(
                "STOP", "Missing or invalid front distance reading", 90
            )

        if inputs.touch:
            self.state = self.IDLE
            self._attempted_turns.clear()
            self._side_avoidance_requested = False
            return self._action(
                "STOP", "Touch interaction: navigation paused", 70
            )

        if not navigation_requested:
            self.state = self.IDLE
            self._attempted_turns.clear()
            self._side_avoidance_requested = False
            return self._action("STOP", "Navigation not requested", 10)

        front_clear = front >= self.OBSTACLE_DISTANCE_CM
        left_valid = self._valid_distance(left)
        right_valid = self._valid_distance(right)

        left_blocked = left_valid and left < self.SIDE_CLEARANCE_CM
        right_blocked = right_valid and right < self.SIDE_CLEARANCE_CM
        side_blocked = left_blocked or right_blocked

        # Clear the repeat-turn guard once the side readings are safe.
        if (
            left_valid
            and right_valid
            and left >= self.SIDE_CLEARANCE_CM
            and right >= self.SIDE_CLEARANCE_CM
        ):
            self._side_turn_suppressed = False

        if self.state == self.IDLE:
            if not front_clear:
                self._begin_blocked(now)
                return self._action(
                    "STOP", "Obstacle detected; stopping first", 80
                )

            if side_blocked:
                self._begin_blocked(now, side_avoidance=True)
                return self._action(
                    "STOP", "Side obstacle detected; stopping first", 80
                )

            self.state = self.MOVING
            return self._action(
                "FORWARD", "Path clear; navigation started", 30, 0.2
            )

        if self.state == self.MOVING:
            if not front_clear:
                self._begin_blocked(now)
                return self._action(
                    "STOP", "Front obstacle detected; stopping first", 80
                )

            if side_blocked and not self._side_turn_suppressed:
                self._begin_blocked(now, side_avoidance=True)
                return self._action(
                    "STOP", "Side obstacle detected; stopping before turn", 80
                )

            return self._action(
                "FORWARD", "Path clear; continuing navigation", 30, 0.2
            )

        if self.state == self.BLOCKED:
            # A side obstacle can require a turn even if the front is clear.
            if (
                front_clear
                and not self._side_avoidance_requested
                and not self._collision_recovery
            ):
                self.state = self.MOVING
                self._attempted_turns.clear()
                return self._action(
                    "FORWARD", "Front path clear; resuming", 30, 0.2
                )

            if now - self._state_started_at < self.BLOCKED_PAUSE_SECONDS:
                return self._action(
                    "STOP", "Waiting before obstacle recovery", 80
                )

            direction = self._choose_turn(
                inputs,
                left_turn_safe=left_turn_safe,
                right_turn_safe=right_turn_safe,
            )

            if direction is None:
                return self._action(
                    "STOP", "No confirmed safe side; remaining stopped", 85
                )

            self.turn_direction = direction
            self._attempted_turns.add(direction)
            self._last_recovery_turn = direction
            self.state = self.TURNING
            self._state_started_at = now

            return self._action(
                direction,
                f"Turning toward clearer side: {direction}",
                80,
                self.TURN_DURATION_SECONDS,
            )

        if self.state == self.TURNING:
            
            if now - self._state_started_at < self.TURN_DURATION_SECONDS:
                return self._action(
                    self.turn_direction,
                    "Completing simulated turn",
                    80,
                    self.TURN_DURATION_SECONDS,
                )

            if front_clear:
                self.state = self.MOVING
                self._collision_recovery = False

                # Keep the recovery turn recorded until forward movement
                # succeeds. A collision on the next move must blacklist it.
                if self._side_avoidance_requested:
                    self._side_turn_suppressed = True

                self._side_avoidance_requested = False

                return self._action(
                    "FORWARD",
                    "Front path clear after turn; resuming cautiously",
                    30,
                    0.2,
                )

        # Preserve the attempted direction during recovery.
            self._attempted_turns.add(self.turn_direction)

            self.state = self.BLOCKED
            self._state_started_at = now

            return self._action(
                "STOP",
                f"Front still blocked after {self.turn_direction}; "
                "stopped and reassessing the alternate side",
                80,
            )

        self.state = self.IDLE
        self._attempted_turns.clear()
        self._side_avoidance_requested = False
        return self._action("STOP", "Unknown state; resetting safely", 90)

    @staticmethod
    def _action(command, reason, priority, duration_seconds=0.0):
        return RobotAction(
            command=command,
            reason=reason,
            priority=priority,
            duration_seconds=duration_seconds,
        )
