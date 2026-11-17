"""Neo Robot Dashboard V3 — 2D world simulation; no hardware connected."""
import math
import time
import tkinter as tk
from tkinter import ttk
from collections import deque

from neo.robot_runtime import NeoRobotRuntime
from neo.simulation import NeoWorld


class DashboardPersonality:
    """Temporary dashboard personality; does not touch persistent memory."""
    def __init__(self):
        self.mood = "happy"
        self.affection = 50
    def update(self, now, dt):
        pass
    def pet(self, now):
        self.affection = min(100, self.affection + 2)


class NeoDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Neo | Robot Control Dashboard V3 — 2D Simulation")
        self.root.geometry("1080x900")
        self.root.minsize(850, 760)
        self.world = NeoWorld()
        self.personality = DashboardPersonality()
        self.runtime = NeoRobotRuntime(personality=self.personality)
        self.started_at = time.monotonic()
        self.last_tick = self.started_at
        self.navigation_requested = False
        self.emergency = False
        self.closed = False
        self.previous_signature = None
        self.event_history = deque(maxlen=200)
        self.last_command = "STOP"
        self.last_status = None
        self.pending_collision = False
        self.manual_override = tk.BooleanVar(value=False)
        self.manual_front = tk.DoubleVar(value=100)
        self.manual_left = tk.DoubleVar(value=100)
        self.manual_right = tk.DoubleVar(value=100)
        self._build_ui()
        self._log("Dashboard V3 started. World-based simulation only.")
        self.pending_collision = False
        self.pending_path_blocked = False
        self._refresh()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="NEO // ROBOT CONTROL", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(main, text="Dashboard V3 • 2D world • simulated sensors • no physical hardware").pack(anchor="w", pady=(2, 8))

        status = ttk.LabelFrame(main, text="Live status", padding=8)
        status.pack(fill="x", pady=4)
        self.mood_label = ttk.Label(status, text="Mood: happy")
        self.mood_label.grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.affection_label = ttk.Label(status, text="Affection: 50")
        self.affection_label.grid(row=0, column=1, sticky="w", padx=12, pady=3)
        self.state_label = ttk.Label(status, text="Navigation: IDLE")
        self.state_label.grid(row=1, column=0, sticky="w", padx=5, pady=3)
        self.command_label = ttk.Label(status, text="Command: STOP")
        self.command_label.grid(row=1, column=1, sticky="w", padx=12, pady=3)
        self.safety_label = ttk.Label(status, text="SAFETY: NAVIGATION PAUSED")
        self.safety_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=3)

                # Always-visible controls: keep these above the simulation world.
        quick_controls = ttk.LabelFrame(
            main,
            text="ROBOT CONTROLS",
            padding=6,
        )
        quick_controls.pack(fill="x", pady=4)

        ttk.Button(
            quick_controls,
            text="▶ START NAVIGATION",
            command=self.start_navigation,
        ).grid(row=0, column=0, padx=4, pady=4, sticky="ew")

        ttk.Button(
            quick_controls,
            text="PAUSE",
            command=self.pause_navigation,
        ).grid(row=0, column=1, padx=4, pady=4, sticky="ew")

        ttk.Button(
            quick_controls,
            text="RESET WORLD",
            command=self.reset_world,
        ).grid(row=0, column=2, padx=4, pady=4, sticky="ew")

        ttk.Button(
            quick_controls,
            text="RESET EMERGENCY STOP",
            command=self.reset_emergency,
        ).grid(row=1, column=0, columnspan=2, padx=4, pady=4, sticky="ew")

        ttk.Button(
            quick_controls,
            text="EMERGENCY STOP",
            command=self.emergency_stop,
        ).grid(row=1, column=2, padx=4, pady=4, sticky="ew")

        for col in range(3):
            quick_controls.columnconfigure(col, weight=1)

        world_frame = ttk.LabelFrame(main, text="2D simulation world (robot moves in this space)", padding=6)
        world_frame.pack(fill="both", expand=True, pady=4)
        self.world_canvas = tk.Canvas(world_frame, height=420, background="#101722", highlightthickness=0)
        self.world_canvas.pack(fill="both", expand=True)

        sensors = ttk.LabelFrame(main, text="World sensor readings (cm)", padding=8)
        sensors.pack(fill="x", pady=4)
        self.sensor_labels = {}
        for col, key in enumerate(("front", "left", "right")):
            self.sensor_labels[key] = ttk.Label(sensors, text=f"{key.title()}: -- cm", width=22)
            self.sensor_labels[key].grid(row=0, column=col, sticky="w", padx=6, pady=3)
        ttk.Checkbutton(sensors, text="Manual sensor override (for controlled tests)", variable=self.manual_override, command=self._manual_changed).grid(row=1, column=0, columnspan=3, sticky="w", padx=5, pady=4)
        self.manual_controls = ttk.Frame(sensors)
        self.manual_controls.grid(row=2, column=0, columnspan=3, sticky="ew")
        self.manual_scales = {}
        for col, key in enumerate(("front", "left", "right")):
            ttk.Label(self.manual_controls, text=key.title()).grid(row=0, column=col * 2, padx=4)
            scale = ttk.Scale(self.manual_controls, from_=0, to=150, variable={"front": self.manual_front, "left": self.manual_left, "right": self.manual_right}[key], orient="horizontal")
            scale.grid(row=0, column=col * 2 + 1, sticky="ew", padx=4)
            self.manual_controls.columnconfigure(col * 2 + 1, weight=1)
            self.manual_scales[key] = scale
        self.manual_controls.grid_remove()

        controls = ttk.LabelFrame(main, text="Controls", padding=8)
        controls.pack(fill="x", pady=4)
        buttons = [
            ("Start navigation", self.start_navigation), ("Pause", self.pause_navigation),
            ("Pet Neo (+ affection)", self.pet_neo), ("Reset world", self.reset_world),
            ("Reset emergency stop", self.reset_emergency), ("EMERGENCY STOP", self.emergency_stop),
        ]
        for i, (label, callback) in enumerate(buttons):
            ttk.Button(controls, text=label, command=callback).grid(row=i // 3, column=i % 3, padx=4, pady=4, sticky="ew")
        for col in range(3):
            controls.columnconfigure(col, weight=1)

        decision = ttk.LabelFrame(main, text="Decision explanation", padding=8)
        decision.pack(fill="x", pady=4)
        self.reason_label = ttk.Label(decision, text="Waiting for runtime update", wraplength=1000, justify="left")
        self.reason_label.pack(anchor="w")
        history = ttk.LabelFrame(main, text="Event history (latest events)", padding=6)
        history.pack(fill="both", expand=True, pady=4)
        self.history_text = tk.Text(history, height=5, wrap="word", state="disabled", font=("Consolas", 9))
        scroll = ttk.Scrollbar(history, orient="vertical", command=self.history_text.yview)
        self.history_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.history_text.pack(side="left", fill="both", expand=True)
        ttk.Label(main, text="SIMULATION ONLY — commands do not control physical motors.", foreground="#b22222").pack(anchor="w", pady=(4, 0))

    def _manual_changed(self):
        if self.manual_override.get():
            self.manual_controls.grid()
            self._log("Manual sensor override enabled.")
        else:
            self.manual_controls.grid_remove()
            self._log("Sensors now come from the 2D world.")

    def _log(self, message):
        stamp = time.monotonic() - self.started_at
        entry = f"[{stamp:7.1f}s] {message}"
        self.event_history.append(entry)
        if not hasattr(self, "history_text"):
            return
        self.history_text.configure(state="normal")
        self.history_text.insert("end", entry + "\n")
        lines = int(self.history_text.index("end-1c").split(".")[0])
        if lines > 200:
            self.history_text.delete("1.0", f"{lines - 200}.0")
        self.history_text.see("end")
        self.history_text.configure(state="disabled")

    def start_navigation(self):
        if self.emergency:
            self._log("Start rejected: reset the emergency stop first.")
            return
        self.navigation_requested = True
        self._log("Navigation requested.")

    def pause_navigation(self):
        self.navigation_requested = False
        self._log("Navigation paused by operator.")

    def pet_neo(self):
        self.personality.pet(time.monotonic() - self.started_at)
        self._log(f"Pet interaction: affection is now {self.personality.affection}.")

    def emergency_stop(self):
        self.emergency = True
        self.navigation_requested = False
        self._log("EMERGENCY STOP activated.")

    def reset_emergency(self):
        self.runtime.reset_emergency_stop()
        self.emergency = False
        self.navigation_requested = False
        self._log("Emergency latch reset. Navigation remains paused.")

    def reset_world(self):
        self.navigation_requested = False
        self.world.reset()
        self._log("World and robot pose reset; navigation paused.")

    def _read_sensors(self):
        if self.manual_override.get():
            return {"front": self.manual_front.get(), "left": self.manual_left.get(), "right": self.manual_right.get()}
        return self.world.sensor_readings()

    def _draw_world(self, readings, command, state):
        c = self.world_canvas
        c.delete("all")
        # Scale world coordinates to the available canvas without distorting proportions.
        cw = max(c.winfo_width(), 500)
        ch = max(c.winfo_height(), 300)
        scale = min((cw - 20) / self.world.WIDTH, (ch - 20) / self.world.HEIGHT)
        ox = (cw - self.world.WIDTH * scale) / 2
        oy = (ch - self.world.HEIGHT * scale) / 2
        c.create_rectangle(ox, oy, ox + self.world.WIDTH * scale, oy + self.world.HEIGHT * scale, outline="#66758a", width=2)
        for x in range(0, self.world.WIDTH + 1, 40):
            xx = ox + x * scale
            c.create_line(xx, oy, xx, oy + self.world.HEIGHT * scale, fill="#202b39")
        for y in range(0, self.world.HEIGHT + 1, 40):
            yy = oy + y * scale
            c.create_line(ox, yy, ox + self.world.WIDTH * scale, yy, fill="#202b39")
        for ob in self.world.obstacles:
            x1, y1 = ox + ob.x * scale, oy + ob.y * scale
            x2, y2 = ox + (ob.x + ob.width) * scale, oy + (ob.y + ob.height) * scale
            c.create_rectangle(x1, y1, x2, y2, fill="#a44d4d", outline="#ef7777", width=1)
            c.create_text((x1+x2)/2, (y1+y2)/2, text=ob.label, fill="#fff0f0", font=("Segoe UI", 8))
        
        
        # Draw the recorded travelled path.
        trail = list(self.world.path)
        current = (self.world.x, self.world.y)

        if not trail or math.hypot(
            trail[-1][0] - current[0],
            trail[-1][1] - current[1],
        ) > 0.01:
            trail.append(current)

        if len(trail) > 1:
            points = [
                (ox + x * scale, oy + y * scale)
                for x, y in trail
            ]

            for start, end in zip(points, points[1:]):
                if math.hypot(
                    end[0] - start[0],
                    end[1] - start[1],
                ) < 0.5:
                    continue

                c.create_line(
                    start[0], start[1],
                    end[0], end[1],
                    fill="#4aa3ff",
                    width=2,
                    capstyle=tk.ROUND,
                )

            # Mark the latest recorded trail point.
            tx, ty = points[-1]
            c.create_oval(
                tx - 2, ty - 2, tx + 2, ty + 2,
                fill="#9ed0ff",
                outline="",
            )


        rx, ry = ox + self.world.x * scale, oy + self.world.y * scale
        r = self.world.ROBOT_RADIUS * scale
        c.create_oval(rx-r, ry-r, rx+r, ry+r, fill="#2f8fda", outline="#d8efff", width=2)
        c.create_text(rx, ry, text="N", fill="white", font=("Segoe UI", 8, "bold"))
        angle = math.radians(self.world.heading)
        tipx = rx + math.sin(angle) * 28 * scale
        tipy = ry - math.cos(angle) * 28 * scale
        c.create_line(rx, ry, tipx, tipy, fill="#7cffb2", width=3, arrow=tk.LAST)
        # Front and side ray visualizations.
        for key, offset, color in (("front", 0, "#ffc857"), ("left", -90, "#7fd1ae"), ("right", 90, "#c29cff")):
            ray = min(float(readings[key]), self.world.SENSOR_RANGE_CM) / self.world.CM_PER_PIXEL
            a = math.radians(self.world.heading + offset)
            ex = rx + math.sin(a) * ray * scale
            ey = ry - math.cos(a) * ray * scale
            c.create_line(rx, ry, ex, ey, fill=color, dash=(3, 3), width=1)
        c.create_text(ox + 8, oy + 8, anchor="nw", text=f"{state} | {command} | pose=({self.world.x:.0f}, {self.world.y:.0f}) | heading={self.world.heading:.0f} deg", fill="#e4edf9", font=("Consolas", 10, "bold"))
        c.create_text(ox + 8, oy + self.world.HEIGHT * scale - 8, anchor="sw", text="Blue trail = travelled path  |  red blocks = obstacles  |  dashed rays = sensors", fill="#b7c7da", font=("Segoe UI", 9))

    def _refresh(self):
        if self.closed:
            return
        now_abs = time.monotonic()
        now = now_abs - self.started_at
        dt = min(max(now_abs - self.last_tick, 0.0), 0.1)
        self.last_tick = now_abs
        readings = self._read_sensors()
        collision_feedback = self.pending_collision
        path_blocked_feedback = self.pending_path_blocked

        self.pending_collision = False
        self.pending_path_blocked = False

        left_turn_safe = None
        right_turn_safe = None

        if not self.manual_override.get():
            left_turn_safe = self.world.can_turn_then_move("TURN_LEFT")
            right_turn_safe = self.world.can_turn_then_move("TURN_RIGHT")

        status = self.runtime.tick(
            now=now,
            obstacle_distance_cm=readings["front"],
            left_distance_cm=readings["left"],
            right_distance_cm=readings["right"],
            navigation_requested=self.navigation_requested,
            emergency_stop=self.emergency,
            collision_detected=collision_feedback,
            path_blocked=path_blocked_feedback,
            left_turn_safe=left_turn_safe,
            right_turn_safe=right_turn_safe,
        )
        
        collision = False
        predictive_block = False

        if not self.manual_override.get():
            if status.command == "FORWARD" and dt > 0:
                # Check the proposed movement before executing it.
                if not self.world.forward_path_is_clear(dt):
                    predictive_block = True
                    self.pending_collision = True
                    self._log(
                        "PREDICTIVE GUARD: forward path is unsafe. "
                        "Movement rejected before collision."
                    )
                else:
                    collision = self.world.step(status.command, dt)
            else:
                collision = self.world.step(status.command, dt)

        if collision:
            self.pending_path_blocked = True
            self._log(
                "COLLISION GUARD: movement rejected. "
                "Navigation will reassess the route."
            )


        self.mood_label.config(text=f"Mood: {status.mood}")
        self.affection_label.config(text=f"Affection: {status.affection}")
        self.state_label.config(text=f"Navigation: {status.navigation_state}")
        self.command_label.config(text=f"Command: {status.command}")
        if status.navigation_state == "EMERGENCY_STOP":
            safety = "SAFETY: EMERGENCY STOP LATCHED"
        elif not self.navigation_requested:
            safety = "SAFETY: NAVIGATION PAUSED"
        elif status.command == "STOP":
            safety = "SAFETY: STOPPED — CHECK REASON"
        else:
            safety = "SAFETY: SIMULATED NAVIGATION ACTIVE"
        self.safety_label.config(text=safety)
        reason = status.reason
        if predictive_block:
            reason += " | Predictive guard rejected unsafe forward movement."
        elif collision:
            reason += " | Collision guard active."

        self.reason_label.config(text=reason)
        for key in ("front", "left", "right"):
            suffix = " (manual)" if self.manual_override.get() else ""
            self.sensor_labels[key].config(text=f"{key.title()}: {readings[key]:.0f} cm{suffix}")
        self._draw_world(readings, status.command, status.navigation_state)
        signature = (status.navigation_state, status.command, status.reason)
        if signature != self.previous_signature:
            self._log(f"{status.navigation_state} | {status.command} | {status.reason}")
            self.previous_signature = signature
        self.last_command = status.command
        self.root.after(50, self._refresh)

    def _close(self):
        self.closed = True
        self.navigation_requested = False
        self.root.destroy()

def main():
    root = tk.Tk()
    NeoDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()