# Neo | Desk Companion

**An interactive desktop companion with voice interaction, emotional responses, gesture recognition, and an evolving personality.**

Neo is a Python-based desktop companion designed to make human-computer interaction more expressive and engaging. It combines a real-time graphical interface with voice processing, emotion-aware responses, webcam-based gesture recognition, and persistent personality attributes.

The project explores how a digital companion can perceive user interactions, respond with different emotional states, and develop a sense of continuity across sessions.

## Features

### Voice Interaction
- Wake-word activation using **"Hey Neo"**.
- Speech recognition using Faster-Whisper.
- Voice activity and wake-word processing using Vosk.
- Text-to-speech responses using Piper TTS, with pyttsx3 as a fallback.
- Conversation-aware responses.

### Emotional Intelligence and Personality
- Emotion detection from conversational input.
- Context-sensitive responses and mood changes.
- Multiple emotional states and personality behaviours.
- Interaction-based affection and mood updates.

### Gesture Recognition
- Webcam-based gesture recognition.
- Hand and gesture tracking using MediaPipe and OpenCV.
- Gesture-driven interaction with Neo.

### Persistent Personality
Neo maintains basic persistent state across sessions, including:
- Affection level.
- Total pet interactions.
- Session count.
- Pet-related mood statistics.

This is currently lightweight state persistence rather than a sophisticated long-term conversational memory system.

### Interactive Desktop Experience
- Animated character rendered using Pygame.
- Multiple facial expressions and reactions.
- Interactive petting and keyboard controls.
- Desktop mode with a transparent, always-on-top window on Windows.
- Idle behaviour and visual feedback.

### Behaviour and Robotics Subsystem
- Decision-making and navigation logic.
- Obstacle-aware movement decisions.
- Robot runtime and personality integration.
- Simulated environment and movement.
- Behaviour event logging and analytics.

## Technology Stack

| Component | Technologies |
|---|---|
| Core application | Python, Pygame |
| Voice recognition | Faster-Whisper, Vosk |
| Speech synthesis | Piper TTS, pyttsx3 |
| Audio processing | NumPy, SciPy, SoundDevice |
| Gesture recognition | MediaPipe, OpenCV |
| Behaviour and simulation | Python |
| Data and analytics | SQLite, CSV |
| Testing | unittest |

## Project Structure

```text
Neo-Companion/
│
├── main.py
├── robot_dashboard.py
├── simulate_neo.py
├── requirements.txt
│
├── neo/
│   ├── decision.py
│   ├── face.py
│   ├── gesture_controller.py
│   ├── navigation.py
│   ├── personality.py
│   ├── robot_interface.py
│   ├── robot_runtime.py
│   ├── settings.py
│   ├── simulation.py
│   ├── sound_effects.py
│   └── voice_companion.py
│
├── data/
│   └── neo_behaviour.py
│
├── analytics/
│   ├── analysis.py
│   └── catalogue.py
│
└── tests/
    ├── test_conversation.py
    ├── test_navigation.py
    ├── test_runtime.py
    └── test_simulation.py
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/Neo-Companion.git
cd Neo-Companion
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

**Windows PowerShell**
```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Download the required AI models

Neo uses external model assets that are intentionally not included in this repository.

- Download and extract the Vosk English model `vosk-model-small-en-us-0.15` into the expected local model directory.
- Faster-Whisper downloads its selected transcription model when initialized, unless it is already cached.
- Download a compatible Piper voice model and its corresponding configuration file if Piper TTS is enabled.

Configure the local model paths according to the application's settings.

**Note:** Model paths and voice configuration may require adjustment for a new installation.

### 5. Run Neo

```bash
python main.py
```

For Windows desktop mode:

```bash
python main.py --desktop
```

## Running Tests

Run the automated test suite:

```bash
python -m unittest discover -s tests -v
```

The current test suite contains 36 passing tests covering conversation logic, navigation, runtime behaviour, and simulation.

Hardware-dependent functionality such as live microphone input, speech transcription, TTS playback, and webcam recognition requires separate runtime testing.

## Current Development Status

Neo is an actively developed prototype.

| Feature | Status |
|---|---|
| Pygame desktop companion | Implemented |
| Wake-word voice interaction | Implemented |
| Speech recognition | Implemented |
| Emotion-aware responses | Implemented |
| Personality behaviour | Implemented |
| Webcam gesture recognition | Implemented |
| Basic persistent state | Implemented |
| Behaviour analytics | Implemented |
| Navigation and simulation | Implemented |
| Physical robot hardware | Planned |

## Roadmap

- Improve conversational memory and contextual continuity.
- Refine speech recognition and interruption handling.
- Expand emotional responses and personality development.
- Improve gesture recognition and multimodal interaction.
- Build a standalone physical hardware version.
- Integrate sensors and actuators with the robotics subsystem.
- Explore more adaptive and autonomous behaviour.

## Platform

The current desktop implementation is primarily developed and tested on **Windows**. Other operating systems may require changes to window management, audio devices, and hardware configuration.

## Project Philosophy

Neo is an exploration of human-computer interaction beyond traditional command-based interfaces.

The long-term goal is to develop a companion that can perceive, react, learn from interactions, and eventually extend beyond the desktop into a physical environment.

---

**Status:** Experimental prototype — actively evolving.