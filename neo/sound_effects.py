
import io
import math
import random
import struct
import wave

import numpy as np
import pygame


class NeoSoundEffects:
    """Longer, expression-specific character chirps for Neo."""

    SAMPLE_RATE = 24000

    # Each sound has its own rhythm, pitch contour and duration.
    PATTERNS = {
        "happy": [
            (570, 790, 0.30, 1.0),
            (790, 710, 0.12, 0.0),
            (740, 980, 0.32, 0.85),
            (950, 1100, 0.20, 0.65),
        ],
        "excited": [
            (620, 900, 0.20, 1.0),
            (780, 1080, 0.18, 0.95),
            (0, 0, 0.10, 0.0),
            (700, 1180, 0.40, 1.0),
        ],
        "curious": [
            (520, 650, 0.25, 0.9),
            (0, 0, 0.12, 0.0),
            (620, 900, 0.40, 0.8),
            (900, 760, 0.22, 0.55),
        ],
        "surprised": [
            (480, 1050, 0.40, 1.0),
            (1050, 880, 0.28, 0.7),
        ],
        "sleepy": [
            (490, 420, 0.48, 0.75),
            (420, 350, 0.50, 0.6),
            (350, 310, 0.40, 0.35),
        ],
        "sad": [
            (510, 430, 0.40, 0.8),
            (430, 390, 0.48, 0.6),
            (390, 340, 0.40, 0.4),
        ],
        "annoyed": [
            (390, 330, 0.24, 0.9),
            (320, 360, 0.16, 0.65),
            (350, 270, 0.34, 0.8),
        ],
    }

    def __init__(self, volume=0.12):
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        self.volume = max(0.0, min(1.0, volume))
        self._sounds = {}
        self._channel = pygame.mixer.Channel(2)
        self._last_expression = None

        for mood, pattern in self.PATTERNS.items():
            sound = pygame.mixer.Sound(buffer=self._build_wav(pattern, mood))
            sound.set_volume(self.volume)
            self._sounds[mood] = sound

    @classmethod
    def _build_wav(cls, pattern, mood):
        sr = cls.SAMPLE_RATE
        pieces = []
        rng = random.Random(mood)

        for start_hz, end_hz, duration, loudness in pattern:
            count = int(sr * duration)

            # Intentional gaps make the rhythm expressive.
            if start_hz == 0:
                pieces.append(np.zeros(count, dtype=np.float32))
                continue

            t = np.arange(count, dtype=np.float32) / sr
            progress = t / max(duration, 0.001)

            # Smooth pitch glide plus a gentle wobble.
            base_freq = start_hz + (end_hz - start_hz) * progress
            vibrato_depth = 5.0 if mood in ("sleepy", "sad") else 10.0
            vibrato = vibrato_depth * np.sin(2 * np.pi * 5.0 * t)
            phase = 2 * np.pi * np.cumsum(base_freq + vibrato) / sr

            # Soft onset and release; no hard-edged note boundaries.
            attack = np.clip(t / 0.07, 0, 1)
            release = np.clip((duration - t) / 0.12, 0, 1)
            envelope = np.minimum(attack, release) ** 0.8

            # Rounded, layered timbre rather than a single pure beep.
            fundamental = np.sin(phase)
            second = np.sin(2.01 * phase + 0.2)
            third = np.sin(3.02 * phase + 0.5)

            if mood == "annoyed":
                wobble = 1 + 0.12 * np.sin(2 * np.pi * 8 * t)
                tone = (fundamental + 0.24 * second + 0.08 * third) * wobble
            elif mood == "sleepy":
                slow_pulse = 0.88 + 0.12 * np.sin(2 * np.pi * 2.2 * t)
                tone = (fundamental + 0.28 * second + 0.06 * third) * slow_pulse
            elif mood == "sad":
                tone = fundamental + 0.32 * second + 0.06 * third
                tone *= 1 + 0.045 * np.sin(2 * np.pi * 6 * t)
            else:
                tone = fundamental + 0.30 * second + 0.10 * third

            # Very quiet breath-like texture softens the synthesized sound.
            breath = np.array(
                [rng.uniform(-1, 1) for _ in range(count)],
                dtype=np.float32,
            )
            breath = np.convolve(
                breath, np.ones(18, dtype=np.float32) / 18, mode="same"
            )
            tone = tone + 0.025 * breath

            segment = tone * envelope * loudness * 0.42
            pieces.append(segment.astype(np.float32))

        audio = np.concatenate(pieces)
        peak = max(float(np.max(np.abs(audio))), 1e-6)
        audio = audio / max(1.0, peak / 0.92)

        pcm = (audio * 32767).astype("<i2").tobytes()
        output = io.BytesIO()

        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sr)
            wav.writeframes(pcm)

        return output.getvalue()

    def play(self, expression):
        """Call only when the displayed expression actually changes."""
        if expression == self._last_expression:
            return

        self._last_expression = expression

        if expression == "neutral":
            self._channel.stop()
            return

        sound = self._sounds.get(expression)
        if sound is None:
            return

        # New expression replaces the previous expression's sound.
        self._channel.stop()
        self._channel.play(sound)

    def stop(self):
        self._channel.stop()
