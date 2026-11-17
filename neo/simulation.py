"""Simple 2D differential-drive world and ray-cast sensors for Neo.

Coordinates are pixels; heading is degrees clockwise from north.
This is a desktop simulation only, not a physical safety controller.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RectObstacle:
    x: float
    y: float
    width: float
    height: float
    label: str = "Obstacle"


class NeoWorld:
    WIDTH = 820
    HEIGHT = 420
    CM_PER_PIXEL = 1.0
    ROBOT_RADIUS = 14.0
    SENSOR_RANGE_CM = 150.0
    FORWARD_SPEED = 70.0       # pixels / second
    TURN_RATE_DEG = 150.0      # degrees / second

    def __init__(self):
        self.obstacles = [
            RectObstacle(100, 75, 130, 24, "North wall"),
            RectObstacle(315, 35, 24, 145, "Central wall"),
            RectObstacle(430, 120, 155, 24, "Barrier"),
            RectObstacle(630, 220, 28, 130, "East wall"),
            RectObstacle(185, 275, 170, 24, "South barrier"),
            RectObstacle(475, 315, 100, 24, "Lower barrier"),
        ]
        self.reset()

    def reset(self):
        self.x = self.WIDTH * 0.5
        self.y = self.HEIGHT - 55
        self.heading = 0.0  # north/up
        self.path = [(self.x, self.y)]
        self.last_collision = False

    def _circle_hits_rect(self, x, y, r, rect):
        closest_x = min(max(x, rect.x), rect.x + rect.width)
        closest_y = min(max(y, rect.y), rect.y + rect.height)
        return (x - closest_x) ** 2 + (y - closest_y) ** 2 < r ** 2

    def collides(self, x, y):
        r = self.ROBOT_RADIUS
        if x < r or y < r or x > self.WIDTH - r or y > self.HEIGHT - r:
            return True
        return any(self._circle_hits_rect(x, y, r, o) for o in self.obstacles)

    
    def turn_is_clear(self, direction, duration):
        """Check whether a simulated turn keeps the robot clear of obstacles."""
        if direction not in ("TURN_LEFT", "TURN_RIGHT"):
            return False

        duration = max(0.0, float(duration))
        sign = -1 if direction == "TURN_LEFT" else 1

        # Sample the full turn, including intermediate headings.
        samples = max(1, math.ceil(duration / (1.0 / 120.0)))
        delta = sign * self.TURN_RATE_DEG * duration / samples

        heading = self.heading
        for _ in range(samples):
            heading = (heading + delta) % 360

            # Rotation is in place in this model. Check the full robot
            # footprint at each sample, not only the sensor rays.
            if self.collides(self.x, self.y):
                return False

        return True

    
    def forward_path_is_clear(self, duration, heading=None):
        """Check the robot's full footprint along a proposed forward path."""
        duration = float(duration)

        if not math.isfinite(duration) or duration < 0:
            return False

        duration = min(duration, 1.0)
        heading = self.heading if heading is None else float(heading)

        if not math.isfinite(heading):
            return False

        steps = max(1, math.ceil(duration / (1.0 / 120.0)))
        sub_dt = duration / steps
        x, y = self.x, self.y
        rad = math.radians(heading)

        for _ in range(steps):
            x += math.sin(rad) * self.FORWARD_SPEED * sub_dt
            y -= math.cos(rad) * self.FORWARD_SPEED * sub_dt

            if self.collides(x, y):
                return False

        return True

    
    def can_turn_then_move(
        self,
        direction,
        turn_duration=0.6,
        forward_duration=0.35,
    ):
        """Check a turn and the following forward path without moving Neo."""
        if direction not in ("TURN_LEFT", "TURN_RIGHT"):
            return False

        try:
            turn_duration = float(turn_duration)
            forward_duration = float(forward_duration)
        except (TypeError, ValueError):
            return False

        if (
            not math.isfinite(turn_duration)
            or not math.isfinite(forward_duration)
            or turn_duration < 0
            or forward_duration < 0
            or turn_duration > 2.0
            or forward_duration > 1.0
        ):
            return False

        # In this simulation, turns are in place. First check the
        # current footprint, then calculate the resulting heading.
        if self.collides(self.x, self.y):
            return False

        sign = -1 if direction == "TURN_LEFT" else 1
        candidate_heading = (
            self.heading
            + sign * self.TURN_RATE_DEG * turn_duration
        ) % 360

        # Check the full footprint along the path after the turn.
        return self.forward_path_is_clear(
            forward_duration,
            heading=candidate_heading,
        )

    
    def step(self, command, dt):
        """Advance the simulated robot in small, collision-checked steps."""
        dt = min(max(float(dt), 0.0), 0.1)
        self.last_collision = False

        # Smaller increments reduce tunnelling through thin obstacles.
        max_step_time = 1.0 / 120.0
        steps = max(1, math.ceil(dt / max_step_time))
        sub_dt = dt / steps

        for _ in range(steps):
            if command == "TURN_LEFT":
                self.heading = (
                    self.heading - self.TURN_RATE_DEG * sub_dt
                ) % 360

            elif command == "TURN_RIGHT":
                self.heading = (
                    self.heading + self.TURN_RATE_DEG * sub_dt
                ) % 360

            elif command == "FORWARD":
                rad = math.radians(self.heading)
                nx = (
                    self.x
                    + math.sin(rad) * self.FORWARD_SPEED * sub_dt
                )
                ny = (
                    self.y
                    - math.cos(rad) * self.FORWARD_SPEED * sub_dt
                )

                if self.collides(nx, ny):
                    self.last_collision = True
                    break

                self.x, self.y = nx, ny

                # Record the accepted position, not the attempted position.
                if not self.path or math.hypot(
                    self.x - self.path[-1][0],
                    self.y - self.path[-1][1],
                ) >= 1.0:
                    self.path.append((self.x, self.y))

            # STOP and unknown commands do not change the pose.

        # Bound memory use during long simulations.
        self.path = self.path[-2000:]
        return self.last_collision

    def _ray_distance(self, angle_deg):
        rad = math.radians(angle_deg)
        step = 2.0
        max_px = self.SENSOR_RANGE_CM / self.CM_PER_PIXEL
        distance = 0.0
        while distance <= max_px:
            px = self.x + math.sin(rad) * distance
            py = self.y - math.cos(rad) * distance
            if self.collides(px, py):
                return round(distance * self.CM_PER_PIXEL, 1)
            distance += step
        return self.SENSOR_RANGE_CM

    def collides_point(self, x, y):
        if x < 0 or y < 0 or x >= self.WIDTH or y >= self.HEIGHT:
            return True
        return any(o.x <= x <= o.x + o.width and o.y <= y <= o.y + o.height for o in self.obstacles)

    def sensor_readings(self):
        # Readings are rays relative to the robot's current heading.
        return {
            "front": self._ray_distance(self.heading),
            "left": self._ray_distance(self.heading - 90),
            "right": self._ray_distance(self.heading + 90),
        }
