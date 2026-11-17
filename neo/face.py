"""Animated expressive face for Neo."""
import math
import random
import pygame

from .settings import (FACE_BG, FACE_OUTLINE, CYAN, PURPLE, GREEN, BLUE,
                       PINK, TRANSITION_DURATION, FACE_RECT)

FACE_RECT = pygame.Rect(*FACE_RECT)

def _rounded(surface, color, rect, radius):
    pygame.draw.rect(surface, color, rect, border_radius=radius)


class NeoFace:
    def __init__(self):
        self.current_mood = "neutral"
        self.previous_mood = "neutral"
        self.transition_start = 0.0
        self.blink_start = None
        self.next_blink = random.uniform(1.2, 2.5)
        self.gaze_x = self.gaze_y = 0.0
        self.glance_x = self.glance_target = 0.0
        self.next_glance = 3.0
        self.look_away_until = 0.0

    def set_mood(self, mood, now):
        if mood == self.current_mood:
            return
        self.previous_mood = self.current_mood
        self.current_mood = mood
        self.transition_start = now

    def update(self, now, dt, mouse_pos):
        mx, my = mouse_pos
        tx = max(-10, min(10, (mx - 450) * 0.035))
        ty = max(-7, min(7, (my - 285) * 0.025))
        if now < self.look_away_until:
            tx = self.glance_target
            ty *= 0.25
        smoothing = min(1.0, dt * 6.0)
        self.gaze_x += (tx - self.gaze_x) * smoothing
        self.gaze_y += (ty - self.gaze_y) * smoothing
        if now >= self.next_glance:
            self.glance_target = random.choice([-8.0, 0.0, 8.0])
            self.look_away_until = now + random.uniform(0.35, 0.8)
            self.next_glance = now + random.uniform(2.5, 5.0)
        target = self.glance_target if now < self.look_away_until else 0.0
        self.glance_x += (target - self.glance_x) * min(1.0, dt * 3.0)
        if self.blink_start is None and now >= self.next_blink:
            self.blink_start = now
        if self.blink_start is not None and now - self.blink_start >=0.20:
            self.blink_start = None
            self.next_blink = now + random.uniform(2.0, 4.8)

    def _blink_amount(self, now):
        if self.blink_start is None:
            return 0.0
        return math.sin(min(1.0, (now - self.blink_start) / 0.20) * math.pi)

    def _draw_expression(self, surface, mood, now):
        breath = math.sin(now * 2.0) * 1.8
        lx = int(385 + self.gaze_x + self.glance_x)
        rx = int(515 + self.gaze_x + self.glance_x)
        ey = int(275 + self.gaze_y + breath)
        my = int(345 + breath)
        color = CYAN
        eye_w, eye_h = 47, 58
        if mood == "happy": eye_h = 38
        elif mood == "sleepy": eye_h = 20
        elif mood == "annoyed": color, eye_h = PURPLE, 43
        elif mood == "surprised": eye_w, eye_h = 43, 74
        elif mood == "curious": eye_h = 52
        elif mood == "sad": color, eye_h = BLUE, 39
        elif mood == "excited": color, eye_h = GREEN, 65
        blink = self._blink_amount(now)
        eye_h = max(3, int(eye_h * (1.0 - 0.97 * blink)))

        for side, x in enumerate((lx, rx)):
            w, h = eye_w, eye_h
            if mood == "curious":
                w, h = (50, 58) if side == 0 else (35, 41)
            if mood == "happy" and blink < 0.15:
                pygame.draw.arc(surface, color, (x-24, ey-14, 48, 28), math.pi, 2*math.pi, 5)
            else:
                _rounded(surface, color, pygame.Rect(x-w//2, ey-h//2,w, h), min(19, h//2))
            # Eyebrows give each emotion a readable silhouette.
            if mood in ("annoyed", "sad", "curious", "surprised", "excited"):
                brow_y = ey - h//2 - 12
                if mood == "annoyed":
                    start, end = ((x-22, brow_y-5), (x+21, brow_y+5))if side == 0 else ((x-21, brow_y+5), (x+22, brow_y-5))
                    pygame.draw.line(surface, PURPLE, start, end, 6)
                elif mood == "sad":
                    start, end = ((x-20, brow_y+4), (x+19, brow_y-4))if side == 0 else ((x-19, brow_y-4), (x+20, brow_y+4))
                    pygame.draw.line(surface, BLUE, start, end, 4)
                elif mood == "curious":
                    pygame.draw.arc(surface, color, (x-19, brow_y-9, 38, 17), math.pi, 2*math.pi, 3)
                elif mood == "surprised":
                    pygame.draw.line(surface, color, (x-15, brow_y-7), (x+15, brow_y-7), 3)
                else:
                    pygame.draw.arc(surface, GREEN, (x-21, brow_y-7, 42, 15), math.pi, 2*math.pi, 3)

        # Mouth geometry changes shape by emotion.
        if mood in ("happy", "excited"):
            h = 38 if mood == "excited" else 29
            pygame.draw.arc(surface, color, (405, my-12, 90, h), math.pi, 2*math.pi, 5)
        elif mood == "sad":
            pygame.draw.arc(surface, color, (414, my+1, 72, 34), 0, math.pi, 5)
        elif mood == "surprised":
            pygame.draw.ellipse(surface, color, (438, my, 24, 32), 4)
        elif mood == "curious":
            pygame.draw.ellipse(surface, color, (442, my+4, 16, 20), 3)
        elif mood == "sleepy":
            pygame.draw.arc(surface, color, (425, my+3, 50, 18), 0, math.pi, 3)
        elif mood == "annoyed":
            pygame.draw.line(surface, color, (425, my+10), (475, my+5), 4)
        else:
            pygame.draw.line(surface, color, (430, my+8), (470, my+8), 3)
        if mood == "excited":
            pygame.draw.circle(surface, GREEN, (365, 330), 3)
            pygame.draw.circle(surface, GREEN, (535, 330), 3)

    def draw(self, screen, now):
        _rounded(screen, FACE_BG, FACE_RECT, 38)
        pygame.draw.rect(screen, FACE_OUTLINE, FACE_RECT, 2, border_radius=38)
        progress = min(1.0, max(0.0, (now - self.transition_start) / TRANSITION_DURATION))
        if progress >= 1.0:
            self._draw_expression(screen, self.current_mood, now)
            return
        old = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        new = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        self._draw_expression(old, self.previous_mood, now)
        self._draw_expression(new, self.current_mood, now)
        old.set_alpha(int(255 * (1.0-progress)))
        new.set_alpha(int(255 * progress))
        screen.blit(old, (0, 0))
        screen.blit(new, (0, 0))