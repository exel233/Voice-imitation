# Voice Imitation Studio

Voice Imitation Studio is a local-first desktop voice cloning and dubbing scaffold built for high-quality workflows, modular model integration, and large local media files.

This repository ships:

- Electron desktop shell
- React + TypeScript + Tailwind creator-style UI
- Python FastAPI backend for inference and media processing orchestration
- Local storage layout for projects, profiles, outputs, jobs, and settings
- Pluggable provider interfaces for TTS, ASR, alignment, source separation, VAD, preprocessing, and export
- A runnable default pipeline with safe fallbacks so the app can start and process files even before stronger models are installed
- Direct audio upload, sample preprocessing, conditioning artifacts, and inline preview playback

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

The backend can auto-resolve a local FFmpeg binary from `imageio-ffmpeg`, so audio/video replacement works more reliably even if `ffmpeg` is not already on your global `PATH`.

The backend launcher prefers the project's local virtual environment automatically:
- Windows: `.venv\\Scripts\\python.exe`
- macOS/Linux: `.venv/bin/python`

The default dev launcher avoids `uvicorn --reload` so the backend stays on the same interpreter instead of spawning a mismatched child process on some Windows setups.

If XTTS is installed in a different Python environment than your `.venv`, the backend launcher will prefer a Python runtime that already has the `TTS` package available so profile-based cloning can use the real XTTS path instead of falling back to the adaptive local provider.

For XTTS-v2, you must explicitly accept Coqui's CPML terms before first model download:

```bash
set COQUI_TOS_AGREED=1
```

Only do this after reviewing and accepting the applicable license terms.

### Run

Backend:

```bash
npm run backend:dev
```

Desktop app:

```bash
npm run dev
```

Desktop/frontend only, if you already started the backend separately:

```bash
npm run dev:ui
```

`npm run dev` is the recommended full-stack command and starts backend + frontend + Electron together.

## Maintenance

Check for orphaned profile artifact folders that no longer have a matching saved profile:

```bash
npm run cleanup:profile-data:check
```

Delete those orphaned `storage/profile_data/<profile_id>` folders:

```bash
npm run cleanup:profile-data
```

## Default Pipeline

- Voice profiles ingest uploaded audio files, preprocess them, store raw and processed samples separately, compute reusable conditioning artifacts, and attach quality warnings
- The preferred profile-based synthesis path is now `xtts`, which uses Coqui XTTS-v2 when the `TTS` package is available and falls back through `openvoice`, `adaptive_clone`, and finally `fallback_generic`
- The bundled default runtime path remains `adaptive_clone` in environments where XTTS/OpenVoice are not installed, and the app records the requested provider versus the actual provider used
- Inline preview is available for processed source samples, quick profile preview, and generated speech outputs through backend-served media routes
- Audio/video replacement uses FFmpeg when available and falls back gracefully when stronger tooling is not installed
- The architecture is ready to swap in XTTS, OpenVoice, faster-whisper, Demucs, MFA, and related quality-oriented providers

## What Was Wrong Before

- Profile creation only copied sample files and metadata
- No speaker embedding or conditioning asset was built
- Synthesis always routed through a generic fallback TTS path
- Uploaded voices did not materially affect the generated output
- The UI could imply a profile was ready even though no real conditioning step had happened

## Current Voice Profile Flow

1. Upload one or more authorized audio files in the desktop app
2. Validate supported format and preprocess to mono `24 kHz` WAV
3. Trim silence and normalize audio conservatively
4. Compute profile artifacts such as average spectrum, MFCC summary, energy, and median pitch
5. Store raw samples, processed samples, profile artifacts, and preview files under `storage/profile_data/<profile_id>/`
6. Generate a quick profile preview and expose processed samples for inline playback

## XTTS / OpenVoice Adapter Notes

- XTTS adapter is integrated in the provider layer and uses Coqui's `TTS("tts_models/multilingual/multi-dataset/xtts_v2")` with uploaded `speaker_wav` references when the `TTS` package is installed
- OpenVoice adapter is also integrated into provider resolution as the next cloning-capable slot, but it requires a local OpenVoice runtime and checkpoints to become available
- Provider resolution is explicit: the app stores both the requested provider and the actual provider used, along with any fallback reason

## Current Limitation

The included `adaptive_clone` backend is profile-conditioned and audibly changes output based on uploaded samples, but it is still not a full neural zero-shot cloner like XTTS-v2 or OpenVoice. It is designed to be an honest, modular default that uses uploaded speaker data now while keeping the code ready for stronger model adapters.

## Recommended Quality Upgrades

- TTS / cloning: XTTS-v2, F5-TTS, StyleTTS2, OpenVoice
- Voice conversion: OpenVoice tone color conversion, RVC, Seed-VC style adapters
- ASR: faster-whisper
- Alignment: Montreal Forced Aligner or WhisperX-style timing adapters
- VAD: Silero VAD
- Source separation: Demucs
- Denoise / enhancement: DeepFilterNet, RNNoise
