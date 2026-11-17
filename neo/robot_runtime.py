
"""Unified, hardware-independent runtime for Basic Mobile Neo."""

from dataclasses import dataclass
from typing import Optional

from neo.navigation import NeoNavigation
from neo.personality import NeoPersonality
from neo.decision import RobotInputs


@dataclass
class NeoRuntimeStatus:
    mood: str
    affection: int
    navigation_state: str
    command: str
    reason: str
    priority: int
    duration_seconds: float
    obstacle_distance_cm: Optional[float]
    left_distance_cm: Optional[float]
    right_distance_cm: Optional[float]
    navigation_requested: bool


class NeoRobotRuntime:
    """Coordinate personality and simulated navigation."""

    def __init__(
        self,
        personality: Optional[NeoPersonality] = None,
        navigation: Optional[NeoNavigation] = None,
    ):
        self.personality = personality or NeoPersonality()
        self.navigation = navigation or NeoNavigation()
        self._last_time = None

    def tick(
        self,
        now: float,
        obstacle_distance_cm=None,
        left_distance_cm=None,
        right_distance_cm=None,
        touch=False,
        emergency_stop=False,
        navigation_requested=False,
        pet_interaction=False,
        collision_detected=False,
        path_blocked=False,
        left_turn_safe=None,
        right_turn_safe=None,

    ) -> NeoRuntimeStatus:
        if self._last_time is not None and now < self._last_time:
            raise ValueError("now must not move backwards")

        dt = 0.0 if self._last_time is None else now - self._last_time
        self._last_time = now

        if pet_interaction:
            self.personality.pet(now)

        self.personality.update(now, dt)

        inputs = RobotInputs(
            obstacle_distance_cm=obstacle_distance_cm,
            touch=touch,
            emergency_stop=emergency_stop,
            left_distance_cm=left_distance_cm,
            right_distance_cm=right_distance_cm,
        )

        action = self.navigation.update(
            now=now,
            inputs=inputs,
            navigation_requested=navigation_requested,
            collision_detected=collision_detected,
            path_blocked=path_blocked,
            left_turn_safe=left_turn_safe,
            right_turn_safe=right_turn_safe
        )

        return NeoRuntimeStatus(
            mood=self.personality.mood,
            affection=self.personality.affection,
            navigation_state=self.navigation.state,
            command=action.command,
            reason=action.reason,
            priority=action.priority,
            duration_seconds=action.duration_seconds,
            obstacle_distance_cm=obstacle_distance_cm,
            left_distance_cm=left_distance_cm,
            right_distance_cm=right_distance_cm,
            navigation_requested=navigation_requested,
        )

    def reset_emergency_stop(self):
        self.navigation.reset_emergency_stop()
