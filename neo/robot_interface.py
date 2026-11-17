
"""Bridge between Neo's personality and robot navigation runtime."""

from dataclasses import dataclass
from typing import Optional

from neo.personality import NeoPersonality
from neo.robot_runtime import NeoRobotRuntime


@dataclass
class RobotStatus:
    mood: str
    command: str
    reason: str
    priority: int
    duration_seconds: float
    obstacle_distance_cm: Optional[float]
    navigation_state: str = "IDLE"
    affection: int = 0
    left_distance_cm: Optional[float] = None
    right_distance_cm: Optional[float] = None


class NeoRobotInterface:
    """Connect Neo's personality to hardware-independent navigation."""

    def __init__(self, personality: NeoPersonality):
        self.personality = personality
        self.runtime = NeoRobotRuntime(personality=personality)
        self.last_action = None

    def decide(
        self,
        obstacle_distance_cm=None,
        touch=False,
        emergency_stop=False,
        navigation_requested=False,
        left_distance_cm=None,
        right_distance_cm=None,
        now=0.0,
    ) -> RobotStatus:
        status = self.runtime.tick(
            now=now,
            obstacle_distance_cm=obstacle_distance_cm,
            left_distance_cm=left_distance_cm,
            right_distance_cm=right_distance_cm,
            touch=touch,
            emergency_stop=emergency_stop,
            navigation_requested=navigation_requested,
        )

        self.last_action = status.command

        return RobotStatus(
            mood=status.mood,
            command=status.command,
            reason=status.reason,
            priority=status.priority,
            duration_seconds=status.duration_seconds,
            obstacle_distance_cm=status.obstacle_distance_cm,
            navigation_state=status.navigation_state,
            affection=status.affection,
            left_distance_cm=status.left_distance_cm,
            right_distance_cm=status.right_distance_cm,
        )

    def reset_emergency_stop(self):
        """Explicitly reset the navigation emergency-stop latch."""
        self.runtime.reset_emergency_stop()
