import sys
import types
import unittest

# The conversation logic is pure Python; stub hardware/runtime dependencies so
# these tests can run on a machine without microphone/TTS packages installed.
for module_name in ("sounddevice", "numpy", "pyttsx3"):
    sys.modules.setdefault(module_name, types.ModuleType(module_name))
scipy = types.ModuleType("scipy")
signal = types.ModuleType("scipy.signal")
signal.resample_poly = lambda *args, **kwargs: None
scipy.signal = signal
sys.modules.setdefault("scipy", scipy)
sys.modules.setdefault("scipy.signal", signal)
vosk = types.ModuleType("vosk")
vosk.KaldiRecognizer = object
vosk.Model = object
sys.modules.setdefault("vosk", vosk)

from neo.voice_companion import ConversationMemory, detect_conversation_emotion

class ConversationTests(unittest.TestCase):
    def test_joke_request(self):
        mood, reply = detect_conversation_emotion("tell me a joke", ConversationMemory())
        self.assertEqual(mood, "happy")
        self.assertTrue(reply)

    def test_identity(self):
        mood, reply = detect_conversation_emotion("who are you", ConversationMemory())
        self.assertEqual(mood, "happy")
        self.assertIn("Neo", reply)

    def test_boundary_is_respected(self):
        memory = ConversationMemory()
        mood, _ = detect_conversation_emotion("leave me alone", memory)
        self.assertTrue(memory.wants_space)
        mood2, reply2 = detect_conversation_emotion("anything", memory)
        self.assertTrue(reply2)

if __name__ == "__main__":
    unittest.main()
