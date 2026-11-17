
"""Hardware-independent decision types and basic decision engine."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RobotInputs:
    obstacle_distance_cm: Optional[float] = None
    touch: bool = False
    emergency_stop: bool = False
    left_distance_cm: Optional[float] = None
    right_distance_cm: Optional[float] = None


@dataclass
class RobotAction:
    command: str
    reason: str
    priority: int
    duration_seconds: float = 0.0


class NeoDecisionEngine:
    """Choose basic actions; navigation handles movement sequences."""

    OBSTACLE_DISTANCE_CM = 20.0

    def decide(
        self,
        inputs: RobotInputs,
        mood: str,
        navigation_requested: bool = False,
    ) -> RobotAction:
        if inputs.emergency_stop:
            return RobotAction(
                "STOP", "Emergency stop activated", 100
            )

        distance = inputs.obstacle_distance_cm

        if not self._valid_distance(distance):
            return RobotAction(
                "STOP", "Missing or invalid front distance", 90
            )

        if distance < self.OBSTACLE_DISTANCE_CM:
            return RobotAction(
                "STOP", "Obstacle detected nearby", 80
            )

        if inputs.touch:
            return RobotAction(
                "STOP", "Responding to touch interaction", 70
            )

        if not navigation_requested:
            return RobotAction(
                "STOP", "Navigation not requested", 10
            )

        if mood in ("sleepy", "curious"):
            reason = (
                "Sleepy: remain stationary"
                if mood == "sleepy"
                else "Curious: pause and observe"
            )
            return RobotAction("STOP", reason, 20)

        if mood == "excited":
            return RobotAction(
                "FORWARD", "Excited: short forward movement", 30, 0.3
            )

        if mood == "happy":
            return RobotAction(
                "FORWARD", "Happy: gentle forward movement", 30, 0.2
            )

        return RobotAction(
            "FORWARD", "Navigation requested: move forward", 30, 0.2
        )

    @staticmethod
    def _valid_distance(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False

        # Reject negative, NaN, and infinite readings.
        import math
        return math.isfinite(value) and value >= 0
