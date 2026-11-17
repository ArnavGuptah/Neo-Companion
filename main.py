import argparse
import ctypes
import ctypes.wintypes
import math
import sys
import time
import re
import pygame
from analytics.catalogue import BehaviourCatalogue
from neo.gesture_controller import GestureController
from neo.sound_effects import NeoSoundEffects

from neo.voice_companion import (
    VoiceCompanion,
    detect_conversation_emotion,
    ConversationMemory,
)

from neo.settings import WIDTH, HEIGHT, FPS, BG, PANEL, WHITE, CYAN, MUTED, TRANSPARENT_KEY
from neo.face import NeoFace
from neo.personality import NeoPersonality

parser = argparse.ArgumentParser(description="Neo | Desk Companion")
parser.add_argument("--desktop", action="store_true", help="borderless, draggable, always-on-top companion mode (Windows)")
args = parser.parse_args()
DESKTOP_MODE = args.desktop

IDLE_CLOCK_SECONDS = 90

VOICE_SESSION_SECONDS = 30

SHORT_COMMANDS = {
    "yes", "no", "stop", "hello", "thanks",
    "thank you", "bye", "goodbye",
}

NOISE_TRANSCRIPTS = {
    "it", "i", "uh", "um", "huh", "hmm", "mm",
}

WAKE_NAMES = {
    "neo", "neyo", "nio", "kneel", "knee",
    "know", "knew", "new", "nemo", "neil",
}

pygame.init()
flags = pygame.NOFRAME if DESKTOP_MODE else 0
screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
pygame.display.set_caption("Neo | Desk Companion")
clock = pygame.time.Clock()
font = pygame.font.SysFont("consolas", 17)
small_font = pygame.font.SysFont("consolas", 13)

clock_font = pygame.font.SysFont("consolas", 88, bold=True)
date_font = pygame.font.SysFont("consolas", 22)
hint_font = pygame.font.SysFont("consolas", 15)

last_interaction_ticks = pygame.time.get_ticks()
clock_mode = False
neo = NeoPersonality()
face = NeoFace()
voice = VoiceCompanion()
conversation = ConversationMemory(max_messages=3)
voice.start()
gesture_controller = GestureController()
gesture_controller.start()
catalogue = BehaviourCatalogue()

session_id = catalogue.start_session(
    "desktop" if "--desktop" in sys.argv else "regular"
)

last_logged_mood = neo.mood

catalogue.start_mood_span(
    session_id,
    neo.mood,
    "session_start",
    0.0,
)

start_ticks = pygame.time.get_ticks()
_dragging = False
_drag_offset = (0, 0)


def elapsed():
    return (pygame.time.get_ticks() - start_ticks) / 1000.0

def mark_interaction():
    global last_interaction_ticks, clock_mode
    last_interaction_ticks = pygame.time.get_ticks()
    clock_mode = False


def force_and_log(expression, now):
    # The central mood tracker logs the transition.
    neo.force_expression(expression, now)
    mark_interaction()
    
def draw_text(text, x, y, color=MUTED, font_obj=font):
    screen.blit(font_obj.render(text, True, color), (x, y))


def rounded_rect(surface, color, rect, radius):
    pygame.draw.rect(surface, color, rect, border_radius=radius)


def draw_character_body(t):
    breath = math.sin(t * 2.0) * 3
    frame = pygame.Rect(245, 110, 410, 380)
    rounded_rect(screen, (9, 12, 19), frame, 46)
    pygame.draw.rect(screen, (54, 65, 84), frame, 2, border_radius=46)
    pygame.draw.arc(screen, (89, 106, 133), pygame.Rect(315, 125, 270, 210), 0.0, math.pi, 7)
    rounded_rect(screen, (73, 85, 109), pygame.Rect(300, 220, 38, 90), 12)
    rounded_rect(screen, (73, 85, 109), pygame.Rect(562, 220, 38, 90), 12)
    hoodie = [(275, 440), (315, 405), (365, 388), (450, 402), (535, 388), (585, 405), (625, 440), (650, 505), (250, 505)]
    hoodie = [(x, int(y + breath if y < 420 else y)) for x, y in hoodie]
    pygame.draw.polygon(screen, (73, 65, 112), hoodie)
    pygame.draw.lines(screen, (120, 105, 174), True, hoodie, 3)
    pygame.draw.arc(screen, (151, 132, 199), pygame.Rect(360, 383, 180, 105), 0.2, math.pi - 0.2, 4)
    pygame.draw.circle(screen, CYAN, (450, 467), 4)


def draw_ui():
    draw_text("NEO // DESK COMPANION", 28, 24, WHITE)
    draw_text("PROTOTYPE 0.3", 28, 49, MUTED, small_font)
    rounded_rect(screen, PANEL, pygame.Rect(28, 535, 844, 86), 14)
    draw_text("INTERACTIONS", 46, 549, WHITE, small_font)
    draw_text("[H] Happy  [A] Annoyed  [S] Sleepy  [N] Neutral", 46, 573, MUTED, small_font)
    draw_text("[SPACE] Surprise  [C] Curious  [D] Sad  [E] Excited", 46, 595, MUTED, small_font)
    draw_text(f"MOOD: {neo.mood.upper()}", 700, 549, CYAN, small_font)
    draw_text(f"PETS: {neo.total_pets}  AFFECTION: {neo.affection}", 650, 573, MUTED, small_font)
    draw_text(f"SESSIONS: {neo.sessions}", 700, 595, MUTED, small_font)

def draw_idle_clock():
    screen.fill((7, 10, 17))

    now = time.localtime()
    time_text = time.strftime("%I:%M", now).lstrip("0")
    am_pm = time.strftime("%p", now)
    date_text = time.strftime("%A, %d %B", now)

    time_surface = clock_font.render(time_text, True, CYAN)
    time_rect = time_surface.get_rect(
        center=(WIDTH // 2, HEIGHT // 2 - 35)
    )
    screen.blit(time_surface, time_rect)

    am_surface = date_font.render(am_pm, True, MUTED)
    screen.blit(
        am_surface,
        am_surface.get_rect(
            midleft=(time_rect.right + 16, time_rect.centery + 17)
        ),
    )

    date_surface = date_font.render(date_text, True, WHITE)
    screen.blit(
        date_surface,
        date_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 45)),
    )

    hint = hint_font.render('SAY "HEY NEO" TO WAKE ME', True, MUTED)
    screen.blit(
        hint,
        hint.get_rect(center=(WIDTH // 2, HEIGHT - 42)),
    )

def enable_windows_desktop_mode():
    """Enable color-key transparency and topmost window styling on Windows."""
    if sys.platform != "win32":
        print("--desktop currently uses Windows-specific window styling; continuing without it.")
        return
    try:
        hwnd = pygame.display.get_wm_info().get("window")
        if not hwnd:
            return
        user32 = ctypes.windll.user32
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TOPMOST = 0x00000008
        LWA_COLORKEY = 0x00000001
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TOPMOST)
        rgb = TRANSPARENT_KEY[0] | (TRANSPARENT_KEY[1] << 8) | (TRANSPARENT_KEY[2] << 16)
        user32.SetLayeredWindowAttributes(hwnd, rgb, 0, LWA_COLORKEY)
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_SHOWWINDOW = 0x0040
        HWND_TOPMOST = -1
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    except Exception as exc:
        print(f"Could not enable full Windows desktop styling: {exc}")


def move_desktop_window(dx, dy):
    if sys.platform != "win32":
        return
    try:
        hwnd = pygame.display.get_wm_info().get("window")
        if hwnd:
            user32 = ctypes.windll.user32
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            user32.SetWindowPos(hwnd, -1, rect.left + dx, rect.top + dy, 0, 0, 0x0001 | 0x0010 | 0x0040)
    except Exception:
        pass




def detect_wake_phrase(phrase):
    """Recognize Neo wake phrases, including common speech-recognition errors."""
    clean = re.sub(r"[^a-z0-9\s]", " ", phrase.lower())
    clean = re.sub(r"\s+", " ", clean).strip()
    words = clean.split()

    if not words:
        return False, phrase

    # Preserve existing alternative wake phrases.
    wake_names = {
        "neo", "neyo", "nio", "nemo", "neil",
        "knew", "know", "new", "kneel", "knee",
        "nilo", "meal", "needle",
    }

    openers = {
        "hey", "he", "hi", "hello", "okay", "ok",
        "a", "the", "they",
    }

    # A recognized name at the beginning is a wake phrase.
    if words[0] in wake_names:
        return True, " ".join(words[1:])

    # Handle common Vosk substitutions such as "hey Neil".
    if len(words) >= 2 and words[0] in openers:
        if words[1] in wake_names:
            return True, " ".join(words[2:])

        # Conservative fuzzy match for the second word only.
        # Require at least 3 characters to reduce accidental triggers.
        import difflib

        candidate = words[1]
        close_match = difflib.get_close_matches(
            candidate,
            ["neo", "neyo", "nemo", "neil", "nio"],
            n=1,
            cutoff=0.78,
        )

        if close_match and len(candidate) <= 5:
            return True, " ".join(words[2:])

    return False, phrase

def main():
    global _dragging, _drag_offset, last_logged_mood
    global last_interaction_ticks, clock_mode
    if DESKTOP_MODE:
        enable_windows_desktop_mode()
    running = True
    last_gesture_time = 0.0
    GESTURE_COOLDOWN = 2.5
    sound_effects = NeoSoundEffects(volume=0.12)

    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        now = elapsed()

        if (
            not clock_mode
            and (pygame.time.get_ticks() - last_interaction_ticks) / 1000
            >= IDLE_CLOCK_SECONDS
        ):
            clock_mode = True

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif clock_mode:
                    mark_interaction()
                elif event.key == pygame.K_h:
                    force_and_log("happy", now)
                elif event.key == pygame.K_a:
                    force_and_log("annoyed", now)
                elif event.key == pygame.K_s:
                    force_and_log("sleepy", now)
                elif event.key == pygame.K_n:
                    force_and_log("neutral", now)
                elif event.key == pygame.K_SPACE:
                    force_and_log("surprised", now)
                elif event.key == pygame.K_c:
                    force_and_log("curious", now)
                elif event.key == pygame.K_d:
                    force_and_log("sad", now)
                elif event.key == pygame.K_e:
                    force_and_log("excited", now)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if clock_mode:
                    mark_interaction()
                    continue

                last_interaction_ticks = pygame.time.get_ticks()
                mx, my = event.pos

                pet_clicked = (
                    245 <= mx <= 655 and 110 <= my <= 510
                    if DESKTOP_MODE
                    else 315 <= mx <= 585 and 165 <= my <= 410
                )

                if pet_clicked:
                    previous_mood = neo.mood
                    affection_before = neo.affection
                    pets_before = neo.total_pets
                    last_pet_before = neo.last_pet_time
                    neo.pet(now)
                    accepted = neo.total_pets > pets_before
                    seconds_since_last_pet = (
                        None
                        if last_pet_before <= -100
                        else now - last_pet_before
                    )

                    catalogue.log_event(
                        session_id,
                        "pet",
                        elapsed_seconds=now,
                        source="pet",
                        previous_mood=previous_mood,
                        mood=neo.mood,
                        affection_before=affection_before,
                        affection_after=neo.affection,
                        total_pets=neo.total_pets,
                        seconds_since_last_pet=seconds_since_last_pet,
                        accepted=accepted,
                        mood_changed=(neo.mood != previous_mood),
                        details=(
                            None if accepted
                            else "Ignored by pet cooldown"
                        ),
                    )

                    if DESKTOP_MODE:
                        _dragging = True
                        _drag_offset = (mx, my)

            elif event.type == pygame.MOUSEMOTION and DESKTOP_MODE and _dragging:
                dx, dy = event.rel
                move_desktop_window(dx, dy)

        gesture = gesture_controller.poll()

        if gesture and now - last_gesture_time >= GESTURE_COOLDOWN:
            
            gesture_moods = {
                "open_palm": ("happy", "Hii! You're here!"),
                "thumbs_up": ("excited", "Yay! Was that a little approval?"),
                "finger_heart": ("happy", "A little heart for me? Aww!"),
            }

            gesture_sounds = {
                "open_palm": "happy",
                "thumbs_up": "excited",
                "finger_heart": "finger_heart",
            }

            if gesture in gesture_moods:
                mood, reply = gesture_moods[gesture]
                sound_effects.play(gesture_sounds[gesture])
                force_and_log(mood, now)
                voice.say(reply, emotion=mood)
                last_gesture_time = now

        
        for phrase in voice.poll():

            if phrase.startswith("__VOICE_UNCERTAIN__:"):
                print("[VOICE] Uncertain transcription:", phrase)
                voice.say(
                    "I didn't quite catch that. Could you say it again?",
                    emotion="curious"
                )
                continue

            if phrase.startswith((
                "__VOICE_ERROR__:",
                "__TTS_ERROR__:",
                "__VOICE_STATUS__:",
            )):
                print(phrase)
                continue

            is_wake, command = detect_wake_phrase(phrase)

            # The idle clock responds only to an explicit wake phrase.
            if clock_mode and not is_wake:
                continue

            if is_wake:
                sound_effects.play("greeting")
                mark_interaction()

                # A wake phrase without a command only wakes Neo.
                if not command:
                    continue

            clean_command = re.sub(
                r"[^a-z0-9'\s]",
                " ",
                (command or phrase).lower()
            )
            clean_command = re.sub(
                r"\s+", " ", clean_command
            ).strip()

            # Reject obvious noise and unclear single-word transcripts.
            if (
                clean_command in NOISE_TRANSCRIPTS
                or (
                    len(clean_command.split()) == 1
                    and clean_command not in SHORT_COMMANDS
                )
            ):
                print("[VOICE] Ignored short/unclear transcript:", phrase)
                continue

            # The command has passed validation.
            # Only now should the 30-second session be extended.
            voice.confirm_command()
            mark_interaction()

            print("You:", command or phrase)

            mood, reply = detect_conversation_emotion(
                command or phrase, conversation
            )

            neo.force_expression(mood, now)
            neo.last_interaction = now
            neo.idle_seconds = 0.0

            print("Neo:", reply)
            voice.say(reply, emotion=mood)

        if not clock_mode:
            neo.update(now, dt)
        
        if neo.mood != last_logged_mood:

            sound_effects.play(neo.mood)
            catalogue.transition_mood(
                session_id,
                elapsed_seconds=now,
                previous_mood=last_logged_mood,
                mood=neo.mood,
                source=neo.mood_source,
                affection=neo.affection,
                total_pets=neo.total_pets,
            )

            last_logged_mood = neo.mood


        if clock_mode:
            draw_idle_clock()
        else:
            face.set_mood(neo.mood, now)
            face.update(now, dt, pygame.mouse.get_pos())
            screen.fill(TRANSPARENT_KEY if DESKTOP_MODE else BG)
            draw_character_body(now)
            face.draw(screen, now)

            if not DESKTOP_MODE:
                draw_ui()
        pygame.display.flip()

    catalogue.close_mood_span(session_id, elapsed())
    catalogue.end_session(session_id)
    gesture_controller.close()
    voice.stop()
    sound_effects.stop()
    pygame.quit()


if __name__ == "__main__":
    main()