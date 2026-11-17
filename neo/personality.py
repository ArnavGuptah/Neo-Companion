"""Neo's lightweight personality, including persistence between runs."""
import json
import random
from pathlib import Path

from .settings import (
    IDLE_MIN_INTERVAL,
    IDLE_MAX_INTERVAL,
    PET_COOLDOWN,
    PET_GAIN_LONG_GAP,
    PET_GAIN_NORMAL_GAP,
    PET_GAIN_QUICK_GAP,
    MAX_AFFECTION,
)

DATA_PATH = Path(__file__).resolve().parent / "neo_memory.json"


class NeoPersonality:
    EXPRESSIONS = {
        "neutral": 0, "happy": 1, "sleepy": 2, "surprised": 3,
        "curious": 4, "annoyed": 5, "sad": 6, "excited": 7,
    }
    IDLE_EXPRESSIONS = [
        ("curious", 2.8), ("happy", 2.5), ("sleepy", 3.5),
        ("surprised", 1.6), ("excited", 2.0), ("neutral", 1.8),
    ]

    def __init__(self):
        self.mood = "neutral"
        self.mood_source = "session_start"
        self.mood_until = 0.0
        self.affection = 0
        self.total_pets = 0
        self.sessions = 0

        # Persistent history of moods produced by accepted pet interactions.
        self.pet_mood_counts = {
            "happy": 0,
            "curious": 0,
            "excited": 0,
        }

        self.last_pet_time = -999.0
        self.last_interaction = 0.0
        self.idle_seconds = 0.0
        self.next_idle_event = random.uniform(5.0, 8.0)
        self._load()
        self.sessions += 1
        self._save()

    def _load(self):
        try:
            data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
            self.affection = max(0, min(100, int(data.get("affection", 0))))
            self.total_pets = max(0, int(data.get("total_pets", 0)))
            self.sessions = max(0, int(data.get("sessions", 0)))
            saved_counts = data.get("pet_mood_counts", {})

            if isinstance(saved_counts, dict):
                for mood in self.pet_mood_counts:
                    try:
                        count = int(saved_counts.get(mood, 0))
                        self.pet_mood_counts[mood] = max(0, min(count, 1_000_000))
                    except (TypeError, ValueError):
                        self.pet_mood_counts[mood] = 0
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    def _save(self):
        data = {
            "affection": self.affection,
            "total_pets": self.total_pets,
            "sessions": self.sessions,
            "pet_mood_counts": self.pet_mood_counts,
        }

        try:
            DATA_PATH.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8",
            )
        except OSError:
            # Neo remains usable if persistence is unavailable.
            pass

    def set_mood(self, mood, now, duration=3.0, source="idle"):
        if mood not in self.EXPRESSIONS:
            return

        self.mood = mood
        self.mood_until = now + duration
        self.mood_source = source

    def pet(self, now):
        # Rejected interactions do not change affection or mood history.
        if now - self.last_pet_time < PET_COOLDOWN:
            return

        previous_pet = self.last_pet_time

        # Record the accepted interaction.
        self.last_pet_time = now
        self.last_interaction = now
        self.idle_seconds = 0.0
        self.total_pets += 1

        # Context-dependent affection reward.
        if previous_pet <= -100:
            affection_gain = PET_GAIN_LONG_GAP
        else:
            gap = now - previous_pet

            if gap >= 10.0:
                affection_gain = PET_GAIN_LONG_GAP
            elif gap >= 2.0:
                affection_gain = PET_GAIN_NORMAL_GAP
            else:
                affection_gain = PET_GAIN_QUICK_GAP

        self.affection = min(
            MAX_AFFECTION,
            self.affection + affection_gain,
        )

        # Rapid accepted interactions trigger excitement.
        if previous_pet > -100 and now - previous_pet < 2.0:
            response = "excited"
            duration = 3.2

        else:
            # Learn from the historical outcomes of pet interactions.
            # Square-root weighting limits how quickly one mood dominates.
            candidates = ["happy", "curious"]
            weights = [
                1.0 + self.pet_mood_counts[mood] ** 0.5
                for mood in candidates
            ]

            response = random.choices(
                candidates,
                weights=weights,
                k=1,
            )[0]

            duration = 2.6

        self.set_mood(response, now, duration, source="pet")

        # Update the history only after choosing this interaction's response.
        self.pet_mood_counts[response] += 1
        self._save()

    def update(self, now, dt):
        self.idle_seconds += dt

        # Preserve expressions triggered by conversation until they expire.
        if self.mood_source == "conversation":
            if now < self.mood_until:
                return

            self.set_mood("neutral", now, 0.0, source="idle")

        elif self.mood != "neutral" and now >= self.mood_until:
            self.set_mood("neutral", now, 0.0, source="idle")

        # Long inactivity can make Neo sleepy.
        if self.idle_seconds >= 45.0 and self.mood == "neutral":
            self.set_mood("sleepy", now, 5.0, source="idle")
            self.idle_seconds = 0.0
            self.next_idle_event = now + random.uniform(6.0, 10.0)
            return

        # Random idle expressions only happen while neutral.
        if self.mood == "neutral" and now >= self.next_idle_event:
            expression, duration = random.choice(self.IDLE_EXPRESSIONS)

            if self.affection >= 30 and random.random() < 0.35:
                expression, duration = "happy", 3.0

            self.set_mood(expression, now, duration, source="idle")
            self.next_idle_event = (
                now + random.uniform(IDLE_MIN_INTERVAL, IDLE_MAX_INTERVAL)
            )
    
    def force_expression(self, expression, now, duration=None):
        if expression not in self.EXPRESSIONS:
            return

        durations = {
            "neutral": 2.0,
            "happy": 7.0,
            "annoyed": 8.0,
            "sleepy": 6.0,
            "surprised": 5.0,
            "curious": 6.0,
            "sad": 12.0,
            "excited": 8.0,
        }

        if duration is None:
            duration = durations.get(expression, 7.0)

        self.set_mood(
            expression,
            now,
            duration,
            source="conversation",
        )
        self.idle_seconds = 0.0
        self.next_idle_event = now + 15.0