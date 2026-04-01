from __future__ import annotations

import contextlib
import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path

from .models import SynthesisControls, TranscriptSegment, VoiceProfile


class TtsProvider:
    name = "base"

    def synthesize(self, text: str, profile: VoiceProfile, controls: SynthesisControls, output_path: Path) -> Path:
        raise NotImplementedError


class AsrProvider:
    name = "base"

    def transcribe_segments(self, input_path: str) -> list[TranscriptSegment]:
        raise NotImplementedError


class FallbackTtsProvider(TtsProvider):
    name = "fallback"

    def synthesize(self, text: str, profile: VoiceProfile, controls: SynthesisControls, output_path: Path) -> Path:
        if self._try_pyttsx3(text, output_path):
            return output_path
        return self._write_placeholder_wave(text, controls, output_path)

    def _try_pyttsx3(self, text: str, output_path: Path) -> bool:
        with contextlib.suppress(Exception):
            import pyttsx3

            engine = pyttsx3.init()
            engine.save_to_file(text, str(output_path))
            engine.runAndWait()
            return output_path.exists() and output_path.stat().st_size > 0
        return False

    def _write_placeholder_wave(self, text: str, controls: SynthesisControls, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        duration = max(2.0, min(len(text) * 0.08 / max(controls.speakingRate, 0.1), 30.0))
        sample_rate = 22050
        base_freq = 180 + controls.pitch * 8
        amplitude = 0.18 + controls.intensity * 0.22
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            frames = []
            for index in range(int(duration * sample_rate)):
                envelope = math.sin(index / sample_rate * math.pi / max(duration, 0.1))
                sample = amplitude * envelope * math.sin(2 * math.pi * base_freq * index / sample_rate)
                frames.append(struct.pack("<h", int(sample * 32767)))
            wav_file.writeframes(b"".join(frames))
        return output_path


class FallbackAsrProvider(AsrProvider):
    name = "fallback"

    def transcribe_segments(self, input_path: str) -> list[TranscriptSegment]:
        duration = probe_duration_seconds(input_path)
        return [
            TranscriptSegment(
                id="seg_001",
                startSec=0,
                endSec=max(1.0, duration),
                text="Fallback transcript placeholder. Install faster-whisper for accurate segmentation.",
                speaker="speaker_1",
            )
        ]


def probe_duration_seconds(input_path: str) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 10.0
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            input_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return 10.0
    with contextlib.suppress(ValueError):
        return float(result.stdout.strip())
    return 10.0
