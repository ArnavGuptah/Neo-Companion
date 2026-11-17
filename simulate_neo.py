
"""End-to-end directional navigation scenarios for Basic Mobile Neo."""

from neo.robot_runtime import NeoRobotRuntime


def run_scenario(name, frames):
    print(f"\n{'=' * 68}")
    print(name)
    print("=" * 68)

    # Reuse one personality object within the scenario.
    runtime = NeoRobotRuntime()

    for frame in frames:
        status = runtime.tick(
            now=frame["time"],
            obstacle_distance_cm=frame.get("front"),
            left_distance_cm=frame.get("left"),
            right_distance_cm=frame.get("right"),
            navigation_requested=frame.get("navigate", True),
            emergency_stop=frame.get("emergency", False),
        )

        print(
            f'{frame["time"]:5.1f}s | {status.navigation_state:15} | '
            f'{status.command:10} | {status.reason}'
        )


run_scenario(
    "SCENARIO 1: LEFT SIDE HAS MORE CLEARANCE",
    [
        {"time": 0.0, "front": 100, "left": 80, "right": 40},
        {"time": 0.2, "front": 10, "left": 80, "right": 40},
        {"time": 0.8, "front": 10, "left": 80, "right": 40},
        {"time": 1.5, "front": 100, "left": 80, "right": 40},
    ],
)

run_scenario(
    "SCENARIO 2: LEFT BLOCKED, RIGHT CLEAR",
    [
        {"time": 0.0, "front": 100, "left": 10, "right": 70},
        {"time": 0.2, "front": 10, "left": 10, "right": 70},
        {"time": 0.8, "front": 10, "left": 10, "right": 70},
        {"time": 1.5, "front": 100, "left": 10, "right": 70},
    ],
)

run_scenario(
    "SCENARIO 3: ALL DIRECTIONS BLOCKED",
    [
        {"time": 0.0, "front": 100, "left": 10, "right": 15},
        {"time": 0.2, "front": 10, "left": 10, "right": 15},
        {"time": 0.8, "front": 10, "left": 10, "right": 15},
        {"time": 1.5, "front": 10, "left": 10, "right": 15},
        {"time": 2.2, "front": 10, "left": 10, "right": 15},
    ],
)

run_scenario(
    "SCENARIO 4: SIDE SENSOR DATA MISSING",
    [
        {"time": 0.0, "front": 100, "left": 80, "right": 60},
        {"time": 0.2, "front": 10, "left": None, "right": 60},
        {"time": 0.8, "front": 10, "left": None, "right": 60},
    ],
)

run_scenario(
    "SCENARIO 5: EMERGENCY STOP",
    [
        {"time": 0.0, "front": 100, "left": 80, "right": 60},
        {
            "time": 0.2,
            "front": 100,
            "left": 80,
            "right": 60,
            "emergency": True,
        },
        {"time": 1.0, "front": 100, "left": 80, "right": 60},
    ],
)
