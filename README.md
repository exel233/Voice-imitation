# Voice Imitation Studio

Voice Imitation Studio is a local-first desktop voice cloning and dubbing scaffold built for high-quality workflows, modular model integration, and large local media files.

This repository ships:

- Electron desktop shell
- React + TypeScript + Tailwind creator-style UI
- Python FastAPI backend for inference and media processing orchestration
- Local storage layout for projects, profiles, outputs, jobs, and settings
- Pluggable provider interfaces for TTS, ASR, alignment, source separation, VAD, preprocessing, and export
- A runnable default pipeline with safe fallbacks so the app can start and process files even before stronger models are installed

## Safety

This application is intended only for voices the user owns or is authorized to use. The product framing, code comments, and UI avoid features aimed at impersonating unauthorized third parties.

## Setup

### Node

```bash
npm install
```

### Python

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
```

### Run

Backend:

```bash
npm run backend:dev
```

Desktop app:

```bash
npm run dev
```

Full stack in one command:

```bash
npm run dev:all
```

## Default Pipeline

- Voice profiles persist authorized user samples and metadata
- TTS uses a runnable fallback provider that tries `pyttsx3` and otherwise emits a placeholder waveform
- Audio/video replacement uses FFmpeg when available and falls back gracefully when stronger tooling is not installed
- The architecture is ready to swap in XTTS, OpenVoice, faster-whisper, Demucs, MFA, and related quality-oriented providers

## Recommended Quality Upgrades

- TTS / cloning: XTTS-v2, F5-TTS, StyleTTS2, OpenVoice
- Voice conversion: OpenVoice tone color conversion, RVC, Seed-VC style adapters
- ASR: faster-whisper
- Alignment: Montreal Forced Aligner or WhisperX-style timing adapters
- VAD: Silero VAD
- Source separation: Demucs
- Denoise / enhancement: DeepFilterNet, RNNoise
