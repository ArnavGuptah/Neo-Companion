import json
import os
import queue
import random
import re
import threading
import time
from collections import deque
from pathlib import Path
import numpy as np
from scipy.signal import resample_poly
import pyttsx3
import sounddevice as sd
from vosk import KaldiRecognizer, Model

MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "models"
    / "vosk-model-small-en-us-0.15"
)

# Device 1 is the confirmed Intel microphone through Windows MME.
MIC_DEVICE = 1
MIC_SAMPLE_RATE = 16000
VOSK_SAMPLE_RATE = 16000
MIC_CHANNELS = 1

# Microphone noise filtering
MIN_AUDIO_RMS = 150
MIN_SPEECH_CHARACTERS = 3

# Short utterances that are often background noise
NOISE_TRANSCRIPTS = {
    "huh",
    "hmm",
    "mm",
    "mhm",
    "uh",
    "um",
    "erm",
    "ah",
    "oh",
}

VALID_MOODS = {
    "neutral", "happy", "curious", "sad",
    "surprised", "excited", "annoyed", "sleepy",
}

RESPONSES = {
    "happy": [
        "Okay, that actually made me smile.",
        "Well, now you've got me smiling.",
        "Aw, that's sweet of you.",
    ],
    "curious": [
        "Okay, now you've got my attention.",
        "Hmm, tell me a little more.",
        "Wait, go on. I'm listening.",
    ],
    "sad": [
        "Oof. That sounds like a lot to deal with.",
        "I'm listening. Take your time.",
        "That sounds rough. I'm here with you.",
    ],
    "surprised": [
        "Wait, seriously? I wasn't expecting that.",
        "Okay, that's a plot twist.",
    ],
    "excited": [
        "That's brilliant! Tell me how it happened.",
        "Look at you making progress! How are you feeling?",
    ],
    "annoyed": [
        "That sounds frustrating. What happened?",
        "Ugh, I can see why that got on your nerves.",
    ],
    "neutral": [
        "Alright, I'm listening.",
        "Okay, what's on your mind?",
    ],
}

def _normalize(text):
    """Normalize speech-recognition text without discarding negation."""
    text = text.lower().replace("â€™", "'").strip()
    text = re.sub(r"[^a-z0-9'\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text

def _has(text, phrases):
    """Match complete phrases rather than accidental substrings."""
    padded = f" {text} "
    return any(f" {phrase} " in padded for phrase in phrases)

class ConversationMemory:
    """Small, explicit conversational state for the last few turns."""

    def __init__(self, max_messages=3):
        self.history = deque(maxlen=max_messages)
        self.current_mood = "neutral"
        self.last_intent = "ordinary"
        self.wants_space = False
        self.last_reply = ""

    def remember(self, text, role="user"):
        clean = _normalize(text)
        if clean:
            self.history.append(f"{role}: {clean}")

    def recent_context(self):
        return " | ".join(self.history)

    def choose_response(self, mood):
        return random.choice(RESPONSES.get(mood, RESPONSES["neutral"]))

def detect_emotion(text):
    """Compatibility helper for older callers."""
    mood, reply = detect_conversation_emotion(text, ConversationMemory())
    return mood, reply

def detect_conversation_emotion(text, memory):
    """Return a mood and conversational response."""
    clean = _normalize(text)

    if not clean:
        return (
            memory.current_mood,
            "I didn't quite catch that. Try saying it once more.",
        )

    boundary_phrases = (
        "don't feel like talking",
        "dont feel like talking",
        "do not feel like talking",
        "don't want to talk",
        "dont want to talk",
        "do not want to talk",
        "don't want to speak",
        "do not want to speak",
        "rather not talk",
        "leave me alone",
        "not in the mood to talk",
        "don't want to discuss it",
    )

    if _has(clean, boundary_phrases):
        mood = (
            "sad"
            if any(word in clean.split() for word in ("sad", "lonely","upset"))
            else "neutral"
        )
        memory.wants_space = True
        memory.last_intent = "boundary"
        reply = random.choice([
            "Okay. I won't push. I'm here if you want me.",
            "That's alright. We can sit quietly for a bit.",
            "Got it. No questions. Take the space you need.",
        ])

    elif memory.wants_space and _has(clean, (
        "but i just said",
        "i said i didn't",
        "i said i did not",
        "i don't want to talk",
        "i dont want to talk",
        "i didn't feel like talking",
        "i did not feel like talking",
    )):
        mood = (
            memory.current_mood
            if memory.current_mood in VALID_MOODS
            else "neutral"
        )
        memory.last_intent = "repair_boundary"
        reply = (
            "You're right. Sorry, I wasn't listening properly. "
            "I won't push you to talk."
        )

    elif _has(clean, (
        "what do you mean",
        "i don't understand",
        "i dont understand",
        "i did not understand",
        "what did you say",
        "say that again",
        "explain that",
    )):
        mood = "curious"
        memory.last_intent = "clarification"
        reply = "My bad, I might've phrased that oddly. Which part should I explain?"

    
    elif _has(clean, (
        "tell me a joke",
        "tell a joke",
        "give me a joke",
        "make me laugh",
        "say something funny",
        "joke",
    )):
        mood = "happy"
        memory.wants_space = False
        memory.last_intent = "joke_request"
        reply = random.choice([
            "Why did the computer go to the doctor? It had a virus!",
            "Why do programmers prefer dark mode? Because light attracts bugs!",
            "I told my computer I needed a break. Now it won't stop sending me KitKat ads.",
        ])

    elif _has(clean, (
        "what can you do",
        "what are your features",
        "what can you help me with",
        "what are you capable of",
    )):
        mood = "curious"
        memory.last_intent = "capabilities"
        reply = (
            "I can chat with you, react to your mood, respond to gestures, "
            "and keep you company on your desktop. I'm still learning,though!"
        )

    elif _has(clean, (
        "who are you",
        "what are you",
        "what is your name",
    )):
        mood = "happy"
        memory.last_intent = "identity"
        reply = random.choice([
            "I'm Neo, your little desktop companion!",
            "I'm Neo! I'm here to keep you company and react to what you say.",
        ])


    # INSERT THE THREE NEW HANDLERS HERE:
    # 1. Joke requests
    # 2. Capabilities
    # 3. Identity

    elif _has(clean, (
        "i feel better",
        "i'm feeling better",
        "im feeling better",
        "feeling a little better",
        "feel a little better",
        "much better now",
        "i'm doing better",
        "im doing better",
        "that's a relief",
        "thats a relief",
        "finally relaxed",
    )):
        mood = "happy"
        memory.wants_space = False
        memory.last_intent = "improving"
        reply = random.choice([
            "I'm glad. No need to rush anything, though.",
            "I'm happy it's easing up a little. What helped?",
            "That's good to hear. Even a little better counts.",
        ])

    elif _has(clean, (
        "i like you",
        "i love you",
        "i like your company",
        "i like being with you",
        "you're sweet",
        "you are sweet",
        "you mean a lot to me",
        "i enjoy talking to you",
    )):
        mood = "happy"
        memory.wants_space = False
        memory.last_intent = "affection"
        reply = random.choice([
            "Aw, that's really sweet. I like keeping you company too.",
            "Well, now you've got me smiling.",
            "I'm glad you feel comfortable hanging out with me.",
            "That's sweet of you to say. I'm right here.",
        ])

    elif _has(clean, (
        "bad day",
        "really bad",
        "terrible day",
        "horrible day",
        "lonely",
        "sad",
        "heartbroken",
        "feeling down",
        "overwhelmed",
        "feeling awful",
        "i feel awful",
    )):
        mood = "sad"
        memory.wants_space = False
        memory.last_intent = "distress"
        reply = random.choice([
            "Ah, I'm sorry. Sounds like today has been a lot.",
            "Oof. I'm here with you. You can tell me if you want.",
            "That sounds rough. We don't have to solve everything right now.",
        ])

    elif _has(clean, (
        "frustrated",
        "angry",
        "annoyed",
        "fed up",
        "irritated",
        "pissed off",
    )):
        mood = "annoyed"
        memory.wants_space = False
        memory.last_intent = "frustration"
        reply = random.choice([
            "That sounds frustrating. What happened?",
            "Ugh, sounds like something really got on your nerves.",
            "Want to work through it, or would you rather leave it fornow?",
        ])

    elif _has(clean, (
        "i passed",
        "i won",
        "i did it",
        "got selected",
        "finished my project",
        "got the job",
        "great news",
        "i succeeded",
    )):
        mood = "excited"
        memory.wants_space = False
        memory.last_intent = "good_news"
        reply = random.choice([
            "Wait, you did it? That's brilliant! Tell me how it happened.",
            "Okay, now that's worth celebrating. How are you feeling?",
            "Look at you making progress! I want the full story.",
        ])

    elif _has(clean, (
        "thank you",
        "thanks",
        "thank you for listening",
        "thanks for your support",
    )):
        mood = "happy"
        memory.last_intent = "thanks"
        reply = random.choice([
            "Of course. I'm glad you talked to me.",
            "Anytime. You don't have to thank me for listening.",
            "I'm happy I could keep you company.",
        ])

    elif _has(clean, (
        "how are you",
        "what do you think",
        "can you explain",
        "tell me about",
    )):
        mood = "curious"
        memory.last_intent = "question"
        reply = random.choice([
            "I'm doing pretty well. What's on your mind?",
            "Doing good! What shall we talk about?",
            "I'm here and listening. What's up?",
        ])

    elif memory.wants_space:
        mood = (
            memory.current_mood
            if memory.current_mood in VALID_MOODS
            else "neutral"
        )
        memory.last_intent = "respecting_boundary"
        reply = random.choice([
            "I'm still here. No pressure to answer.",
            "We can just have a quiet moment.",
            "No need to explain anything.",
        ])

    elif memory.current_mood in ("sad", "annoyed"):
        mood = memory.current_mood
        memory.last_intent = "follow_up"
        reply = random.choice([
            "I'm listening. Take your time.",
            "Go on, I'm here with you.",
            "What happened next?",
        ])

    else:
        mood = "curious"
        memory.last_intent = "ordinary"
        reply = random.choice([
            "Okay, tell me a little more.",
            "Hmm, go on.",
            "Alright, I'm listening.",
        ])

    memory.remember(clean, role="user")
    memory.remember(reply, role="neo")
    memory.current_mood = mood
    memory.last_reply = reply

    return mood, reply

class VoiceCompanion:
    """Vosk input and pyttsx3 output on independent worker threads."""

    # Ignore only obvious incomplete fragments. Legitimate short commands
    # such as "stop", "hello", and "yes" remain usable.
    INCOMPLETE_FRAGMENTS = {
        "i'm", "im", "i am",
        "i've", "ive", "i have",
        "i'd", "id", "i'll", "ill",
        "uh", "um", "erm", "hmm", "mm",
        "the", "a", "an", "and", "but",
        "because", "so", "well", "you know",
    }

    def __init__(self):
        self.results = queue.Queue()
        self.speech_queue = queue.Queue(maxsize=3)
        # 64 x 100 ms blocks gives a bounded 6.4-second safety buffer.
        self.audio_queue = queue.Queue(maxsize=64)
        self.dropped_audio_blocks = 0
        self.running = False
        self._threads = []
        self._start_lock = threading.Lock()
        self._speaking_event = threading.Event()
        self._processing_event = threading.Event()
        self._accepted_command_event = threading.Event()
        self._status_lock = threading.Lock()
        self._last_status_time = 0.0

    def start(self):
        with self._start_lock:
            if self.running:
                return

            self.running = True
            self._threads = [
                threading.Thread(
                    target=self._listen,
                    name="NeoListener",
                    daemon=True,
                ),
                threading.Thread(
                    target=self._speak,
                    name="NeoSpeaker",
                    daemon=True,
                ),
            ]

            for thread in self._threads:
                thread.start()
    
    def confirm_command(self):
        """Extend the wake session only after main.py accepts a command."""
        self._accepted_command_event.set()

    def _listen(self):
        try:
            if not MODEL_PATH.exists():
                raise FileNotFoundError(f"Vosk model not found: {MODEL_PATH}")

            from faster_whisper import WhisperModel

            vosk_model = Model(str(MODEL_PATH))
            print("[VOICE] Loading faster-whisper base.en (CPU int8)...")
            whisper_model = WhisperModel(
                "base.en",
                device="cpu",
                compute_type="int8",
                cpu_threads=4,
                num_workers=1,
            )
            print("[VOICE] Faster-Whisper base.en loaded.")

            WAKE_SESSION_SECONDS = 30
            WAKE_PHRASES = {
                "hey neo", "hi neo", "hello neo", "okay neo", "ok neo",
            }
            wake_grammar = json.dumps([
                "hey neo", "hi neo", "hello neo", "okay neo", "ok neo", "[unk]",
            ])
            wake_recognizer = KaldiRecognizer(
                vosk_model, VOSK_SAMPLE_RATE, wake_grammar
            )
            # Vosk is retained for low-cost wake-word detection and endpointing.
            endpoint_recognizer = KaldiRecognizer(
                vosk_model, VOSK_SAMPLE_RATE
            )

            recognizer = wake_recognizer
            awake = False
            awake_until = 0.0
            utterance_chunks = []
            max_utterance_bytes = VOSK_SAMPLE_RATE * 2 * 15

            def on_audio(indata, frames, time_info, status):
                if not self.running:
                    return

                if status:
                    current = time.monotonic()
                    with self._status_lock:
                        if current - self._last_status_time >= 5.0:
                            self.results.put(f"__VOICE_STATUS__:{status}")
                            self._last_status_time = current

                # Do not accumulate speech while Neo is speaking or Whisper is
                # decoding the previous utterance. This prevents stale backlog.
                if self._speaking_event.is_set() or self._processing_event.is_set():
                    return

                block = bytes(indata)
                try:
                    self.audio_queue.put_nowait(block)
                except queue.Full:
                    # Prefer recent audio over a growing delay behind real time.
                    try:
                        self.audio_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self.dropped_audio_blocks += 1
                    try:
                        self.audio_queue.put_nowait(block)
                    except queue.Full:
                        pass

            def transcribe_command(audio_bytes):
                audio_i16 = np.frombuffer(audio_bytes, dtype=np.int16)
                if audio_i16.size < int(VOSK_SAMPLE_RATE * 0.25):
                    return

                rms = float(np.sqrt(np.mean(audio_i16.astype(np.float32) ** 2)))
                if rms < MIN_AUDIO_RMS:
                    print(f"[VOICE] Ignored quiet audio (RMS {rms:.0f}).")
                    return

                self._processing_event.set()
                self._clear_audio_queue()
                try:
                    audio_f32 = audio_i16.astype(np.float32) / 32768.0
                    segments, info = whisper_model.transcribe(
                        audio_f32,
                        language="en",
                        beam_size=5,
                        condition_on_previous_text=False,
                        vad_filter=False,
                    )
                    segments = list(segments)
                    transcript = " ".join(
                        segment.text.strip() for segment in segments
                        if segment.text.strip()
                    ).strip()

                    if not transcript:
                        self.results.put("__VOICE_UNCERTAIN__:")
                        return

                    logprobs = [s.avg_logprob for s in segments]
                    no_speech = [s.no_speech_prob for s in segments]
                    compression = [s.compression_ratio for s in segments]
                    avg_logprob = (
                        sum(logprobs) / len(logprobs) if logprobs else -99.0
                    )
                    max_no_speech = max(no_speech, default=1.0)
                    max_compression = max(compression, default=99.0)
                    language_probability = getattr(info, "language_probability", 1.0)

                    # Conservative rejection: ask for a repeat rather than
                    # assigning an emotion to a transcript Whisper itself doubts.
                    uncertain = (
                        avg_logprob < -1.05
                        or max_no_speech > 0.65
                        or max_compression > 2.4
                        or language_probability < 0.50
                    )
                    if uncertain:
                        print(
                            "[VOICE] Uncertain transcription:", repr(transcript),
                            f"(logprob={avg_logprob:.2f}, "
                            f"no_speech={max_no_speech:.2f})",
                        )
                        self.results.put(f"__VOICE_UNCERTAIN__:{transcript}")
                        return

                    normalized = _normalize(transcript)
                    if (
                        normalized in self.INCOMPLETE_FRAGMENTS
                        or normalized in NOISE_TRANSCRIPTS
                    ):
                        self.results.put(f"__VOICE_UNCERTAIN__:{transcript}")
                        return

                    print("[VOICE FINAL]", transcript)
                    self.results.put(transcript)
                except Exception as exc:
                    self.results.put(f"__VOICE_STATUS__:transcription failed: {exc}")
                finally:
                    self._clear_audio_queue()
                    self._processing_event.clear()

            # Fixed 100 ms blocks reduce callback churn on the MME input device.
            with sd.RawInputStream(
                device=MIC_DEVICE,
                samplerate=MIC_SAMPLE_RATE,
                blocksize=1600,
                dtype="int16",
                channels=MIC_CHANNELS,
                latency="high",
                callback=on_audio,
            ):
                print(
                    f"[VOICE] Using input device {MIC_DEVICE} "
                    f"at {MIC_SAMPLE_RATE} Hz (MME)"
                )
                print("[VOICE] Waiting for 'Hey Neo'.")

                last_partial = ""
                while self.running:
                    # main.py signals this only after a command passes its filters.
                    if self._accepted_command_event.is_set():
                        awake_until = time.monotonic() + WAKE_SESSION_SECONDS
                        self._accepted_command_event.clear()

                    try:
                        raw_data = self.audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue

                    if awake and time.monotonic() >= awake_until:
                        awake = False
                        recognizer = wake_recognizer
                        wake_recognizer.Reset()
                        endpoint_recognizer.Reset()
                        utterance_chunks.clear()
                        self._clear_audio_queue()
                        last_partial = ""
                        print("[VOICE] Session expired. Waiting for 'Hey Neo'.")

                    audio = np.frombuffer(raw_data, dtype=np.int16)
                    if audio.size == 0:
                        continue

                    if not awake:
                        if recognizer.AcceptWaveform(raw_data):
                            phrase = json.loads(recognizer.Result()).get("text", "").strip()
                            last_partial = ""
                            if _normalize(phrase) in WAKE_PHRASES:
                                print("[VOICE] Wake phrase detected:", phrase)
                                self.results.put("hey neo")
                                awake = True
                                awake_until = time.monotonic() + WAKE_SESSION_SECONDS
                                endpoint_recognizer.Reset()
                                recognizer = endpoint_recognizer
                                utterance_chunks.clear()
                                print("[VOICE] Neo is awake. Listening for commands.")
                        continue

                    utterance_chunks.append(raw_data)
                    endpoint_detected = recognizer.AcceptWaveform(raw_data)
                    utterance_size = sum(map(len, utterance_chunks))
                    forced_endpoint = utterance_size >= max_utterance_bytes

                    if endpoint_detected or forced_endpoint:
                        audio_bytes = b"".join(utterance_chunks)
                        utterance_chunks.clear()
                        recognizer.Reset()
                        last_partial = ""
                        transcribe_command(audio_bytes)
                    else:
                        partial = json.loads(recognizer.PartialResult()).get("partial", "").strip()
                        if partial and partial != last_partial:
                            # Partial Vosk text is diagnostic only; Whisper supplies
                            # the final transcript sent to the conversation engine.
                            print("[VOICE PARTIAL]", partial)
                            last_partial = partial

        except Exception as exc:
            if self.running:
                self.results.put(f"__VOICE_ERROR__:{exc}")

    def _clear_audio_queue(self):
        """Discard audio captured before a recognition-mode change."""
        while True:
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

    def _speak(self):
        """Speak with Piper Amy, using emotion-aware delivery and Zirafallback."""
        piper_voice = None

        voice_dir = Path(
            os.getenv(
                "NEO_PIPER_VOICE_DIR",
                str(Path(__file__).resolve().parent.parent / "voices")
            )
        )

        model_path = voice_dir / "en_US-amy-medium.onnx"
        config_path = voice_dir / "en_US-amy-medium.onnx.json"

        # Emotion profiles: playback volume, Zira speaking rate, Zira volume.
        emotion_profiles = {
            # Piper gain, Zira speaking rate, Zira volume
            "neutral":   (1.00, 145, 0.90),
            "happy":     (1.04, 152, 0.92),
            "curious":   (0.98, 148, 0.88),
            "sad":       (0.84, 125, 0.76),
            "surprised": (1.03, 158, 0.90),
            "excited":   (1.10, 165, 1.00),
            "annoyed":   (1.02, 155, 0.90),
            "sleepy":    (0.82, 118, 0.72),
            "caring":    (0.86, 125, 0.76),
        }

        try:
            from piper import PiperVoice

            if not model_path.is_file() or not config_path.is_file():
                raise FileNotFoundError(
                    "Piper Amy model or configuration file is missing."
                )

            piper_voice = PiperVoice.load(
                str(model_path),
                config_path=str(config_path),
            )
            print("[TTS] Piper Amy voice loaded.")

        except Exception as exc:
            print(f"[TTS] Piper unavailable; using Zira: {exc}")

        while self.running:
            try:
                message = self.speech_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if message is None:
                break

            # Support both the new dictionary format and older queued strings.
            if isinstance(message, dict):
                text = str(message.get("text", "")).strip()
                emotion = str(message.get("emotion", "neutral")).lower().strip()
            else:
                text = str(message).strip()
                emotion = "neutral"

            if not text:
                continue

            if emotion not in emotion_profiles:
                emotion = "neutral"

            gain, zira_rate, zira_volume = emotion_profiles[emotion]
            engine = None

            self._speaking_event.set()
            self._clear_audio_queue()

            try:
                print(f"[TTS] Speaking ({emotion}): {text}")

                if piper_voice is not None:
                    try:
                        chunks = list(piper_voice.synthesize(text))

                        if not chunks:
                            raise RuntimeError("Piper generated no audio.")

                        sample_rate = chunks[0].sample_rate
                        audio_bytes = b"".join(
                            chunk.audio_int16_bytes for chunk in chunks
                        )

                        if not audio_bytes:
                            raise RuntimeError("Piper generated empty audio.")

                        # Adjust loudness without changing Amy's pitch.
                        audio = np.frombuffer(
                            audio_bytes, dtype=np.int16
                        ).astype(np.float32)

                        audio = np.clip(
                            audio * gain, -32768, 32767
                        ).astype(np.int16)

                        # A tiny pause after calmer or more expressivereplies.
                        if emotion in ("sleepy", "caring"):
                            silence = np.zeros(
                                int(sample_rate * 0.18), dtype=np.int16
                            )
                            audio = np.concatenate((audio, silence))

                        sd.play(audio, samplerate=sample_rate)
                        sd.wait()

                    except Exception as exc:
                        try:
                            sd.stop()
                        except Exception:
                            pass

                        print(f"[TTS] Piper failed; switching to Zira:{exc}")
                        piper_voice = None

                if piper_voice is None:
                    engine = pyttsx3.init()

                    voices = engine.getProperty("voices") or []
                    zira = next(
                        (
                            voice for voice in voices
                            if "zira" in voice.name.lower()
                        ),
                        None,
                    )

                    if zira:
                        engine.setProperty("voice", zira.id)

                    engine.setProperty("rate", zira_rate)
                    engine.setProperty("volume", zira_volume)
                    engine.say(text)
                    engine.runAndWait()

                print("[TTS] Finished.")

            except Exception as exc:
                self.results.put(f"__TTS_ERROR__:{exc}")
                print(f"[TTS ERROR] {exc}")

            finally:
                if engine is not None:
                    try:
                        engine.stop()
                    except Exception:
                        pass

                self._clear_audio_queue()
                self._speaking_event.clear()

    def poll(self):
        phrases = []

        while True:
            try:
                phrases.append(self.results.get_nowait())
            except queue.Empty:
                break

        return phrases
    
    def say(self, text, emotion="neutral"):
        if not self.running or not text:
            return

        # Discard stale pending replies; keep only the latest.
        while True:
            try:
                self.speech_queue.get_nowait()
            except queue.Empty:
                break

        # Store the emotion with the reply for the speaker thread.
        allowed_emotions = {
            "neutral",
            "happy",
            "curious",
            "sad",
            "surprised",
            "excited",
            "annoyed",
            "sleepy",
            "caring",
        }
        
        emotion = emotion.lower().strip()
        if emotion not in allowed_emotions:
            emotion = "neutral"

        message = {
            "text": str(text),
            "emotion": emotion,
        }

        try:
            self.speech_queue.put_nowait(message)
        except queue.Full:
            self.results.put("__TTS_ERROR__:speech queue is full")

    def stop(self):
        self.running = False

        while True:
            try:
                self.speech_queue.get_nowait()
            except queue.Empty:
                break

        try:
            self.speech_queue.put_nowait(None)
        except queue.Full:
            pass

        for thread in self._threads:
            if thread.is_alive():
                thread.join(timeout=1.5)