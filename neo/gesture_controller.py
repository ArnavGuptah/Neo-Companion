import cv2
import mediapipe as mp
import math
import threading
import time


class GestureController:
    def __init__(self, camera_index=0):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            model_complexity=0,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.5,
        )

        self.camera_index = camera_index
        self.camera = None
        self.last_gesture = "none"
        self._candidate_gesture = "none"
        self._candidate_frames = 0
        self._stable_gesture = "none"
        self._required_stable_frames = 3

        self._none_frames = 0
        self._required_release_frames = 8

        self._pending_gesture = None
        self._last_emitted_at = 0.0
        self._gesture_cooldown = 2.0
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return True

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="NeoGestureWorker",
            daemon=True,
        )
        self._thread.start()
        return True

    @staticmethod
    def _distance(a, b):
        return math.hypot(a.x - b.x, a.y - b.y)

    def _classify(self, hand):
        lm = hand.landmark

        def extended(tip, pip, mcp):
            tip_to_wrist = self._distance(lm[tip], lm[0])
            pip_to_wrist = self._distance(lm[pip], lm[0])
            mcp_to_wrist = self._distance(lm[mcp], lm[0])

            return (
                tip_to_wrist > pip_to_wrist * 1.10
                and tip_to_wrist > mcp_to_wrist * 1.25
            )

        index_up = extended(8, 6, 5)
        middle_up = extended(12, 10, 9)
        ring_up = extended(16, 14, 13)
        pinky_up = extended(20, 18, 17)

        palm_size = max(self._distance(lm[5], lm[17]), 0.001)

        thumb_extended = (
            self._distance(lm[4], lm[17])
            > self._distance(lm[3], lm[17]) * 1.10
        )

        thumb_open = (
            self._distance(lm[4], lm[5]) > palm_size * 0.55
        )

        if (
            index_up and middle_up and ring_up and pinky_up
            and thumb_open
        ):
            return "open_palm"

        if (
            thumb_extended
            and not index_up and not middle_up
            and not ring_up and not pinky_up
            and lm[4].y < lm[3].y
        ):
            return "thumbs_up"

        return "none"
    
    def _classify_two_hands(self, hands):
        """Detect a heart made with both hands."""
        if not hands or len(hands) < 2:
            return "none"

        hand_a = hands[0].landmark
        hand_b = hands[1].landmark

        # Normalize distances using the size of each palm.
        palm_a = max(self._distance(hand_a[5], hand_a[17]), 0.001)
        palm_b = max(self._distance(hand_b[5], hand_b[17]), 0.001)
        palm_size = (palm_a + palm_b) / 2

        # The index fingertips should meet near the top of the heart.
        index_gap = self._distance(hand_a[8], hand_b[8]) / palm_size

        # The thumb tips should meet near the bottom of the heart.
        thumb_gap = self._distance(hand_a[4], hand_b[4]) / palm_size

        # The index tips should be above the thumb tips in the image.
        index_y = (hand_a[8].y + hand_b[8].y) / 2
        thumb_y = (hand_a[4].y + hand_b[4].y) / 2

        # Reject hands that are too far apart or in an implausible arrangement.
        if (
            index_gap < 1.20
            and thumb_gap < 1.00
            and index_y < thumb_y + 0.05
        ):
            return "finger_heart"

        return "none"


    def _update_gesture(self, gesture):
        """Debounce gestures and emit each deliberate pose once."""
        now = time.monotonic()

        if gesture == "none":
            self._none_frames += 1

            # Keep the previous stable pose through brief detection gaps.
            if self._none_frames < self._required_release_frames:
                return

            self._candidate_gesture = "none"
            self._candidate_frames = 0
            self._stable_gesture = "none"
            self.last_gesture = "none"
            return

        self._none_frames = 0

        if gesture == self._candidate_gesture:
            self._candidate_frames += 1
        else:
            self._candidate_gesture = gesture
            self._candidate_frames = 1

        if self._candidate_frames < self._required_stable_frames:
            return

        if gesture == self._stable_gesture:
            return

        self._stable_gesture = gesture
        self.last_gesture = gesture

        # Emit only after the gesture is stable and the cooldown has elapsed.
        if now - self._last_emitted_at < self._gesture_cooldown:
            return

        self._pending_gesture = gesture
        self._last_emitted_at = now


    def _run(self):
        try:
            self.camera = cv2.VideoCapture(
                self.camera_index, cv2.CAP_DSHOW
            )

            if not self.camera.isOpened():
                self.camera.release()
                self.camera = cv2.VideoCapture(self.camera_index)

            if not self.camera.isOpened():
                print("[GESTURE] Could not open webcam.")
                return

            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            print("[GESTURE] Background webcam started.")

            while not self._stop_event.is_set():
                ok, frame = self.camera.read()
                if not ok:
                    time.sleep(0.05)
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                rgb.flags.writeable = False
                result = self.hands.process(rgb)
                
                gesture = "none"
                detected_hands = result.multi_hand_landmarks or []

                if len(detected_hands) >= 2:
                    gesture = self._classify_two_hands(detected_hands)

                if gesture == "none" and detected_hands:
            # Preserve existing single-hand gestures.
                    single_hand_gestures = [
                        self._classify(hand) for hand in detected_hands
                    ]

                    if "open_palm" in single_hand_gestures:
                        gesture = "open_palm"
                    elif "thumbs_up" in single_hand_gestures:
                        gesture = "thumbs_up"

                with self._lock:
                    self._update_gesture(gesture)   

        except Exception as exc:
            print(f"[GESTURE] Worker error: {exc}")

        finally:
            if self.camera is not None:
                self.camera.release()
                self.camera = None
            self.hands.close()
            print("[GESTURE] Background webcam stopped.")

    def poll(self):
        """Return a newly detected gesture once, or None."""
        with self._lock:
            gesture = self._pending_gesture
            self._pending_gesture = None
        return gesture

    def close(self):
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        cv2.destroyAllWindows()