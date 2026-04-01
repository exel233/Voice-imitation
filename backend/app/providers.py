from __future__ import annotations

import contextlib
import importlib.util
import math
import os
import shutil
import struct
import subprocess
import wave
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from scipy import signal

from .audio_pipeline import TARGET_SAMPLE_RATE, load_conditioning_artifact, normalize_audio
from .config import env_str
from .media_tools import resolve_ffprobe
from .models import SynthesisControls, TranscriptSegment, VoiceProfile


class TtsProvider:
    name = "base"
    cloning_capable = False
    label = "Unknown"

    def synthesize(self, text: str, profile: VoiceProfile, controls: SynthesisControls | None, output_path: Path) -> Path:
        raise NotImplementedError

    def is_available(self) -> bool:
        return True

    def unavailable_reason(self) -> str:
        return "Unknown"


class AsrProvider:
    name = "base"

    def transcribe_segments(self, input_path: str) -> list[TranscriptSegment]:
        raise NotImplementedError


class GenericFallbackTtsProvider(TtsProvider):
    name = "fallback_generic"
    label = "Generic fallback"
    cloning_capable = False

    def synthesize(self, text: str, profile: VoiceProfile, controls: SynthesisControls | None, output_path: Path) -> Path:
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

    def _write_placeholder_wave(self, text: str, controls: SynthesisControls | None, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        speaking_rate = controls.speakingRate if controls else 1.0
        intensity = controls.intensity if controls else 0.5
        pitch = controls.pitch if controls else 0.0
        duration = max(2.0, min(len(text) * 0.08 / max(speaking_rate, 0.1), 30.0))
        base_freq = 180 + pitch * 8
        amplitude = 0.18 + intensity * 0.22
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(TARGET_SAMPLE_RATE)
            frames = []
            for index in range(int(duration * TARGET_SAMPLE_RATE)):
                envelope = math.sin(index / TARGET_SAMPLE_RATE * math.pi / max(duration, 0.1))
                sample = amplitude * envelope * math.sin(2 * math.pi * base_freq * index / TARGET_SAMPLE_RATE)
                frames.append(struct.pack("<h", int(sample * 32767)))
            wav_file.writeframes(b"".join(frames))
        return output_path


class AdaptiveCloneTtsProvider(TtsProvider):
    name = "adaptive_clone"
    label = "Adaptive profile-conditioned synthesis"
    cloning_capable = True

    def __init__(self) -> None:
        self.base = GenericFallbackTtsProvider()

    def synthesize(self, text: str, profile: VoiceProfile, controls: SynthesisControls | None, output_path: Path) -> Path:
        temp_base = output_path.with_name(f"{output_path.stem}_base.wav")
        self.base.synthesize(text, profile, controls, temp_base)

        if not profile.conditioningArtifactPath:
            shutil.copy2(temp_base, output_path)
            return output_path

        conditioned = self._condition_with_profile(temp_base, profile, controls)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(output_path, conditioned, TARGET_SAMPLE_RATE)
        with contextlib.suppress(FileNotFoundError):
            temp_base.unlink()
        return output_path

    def _condition_with_profile(self, base_path: Path, profile: VoiceProfile, controls: SynthesisControls | None) -> np.ndarray:
        base_audio, _ = librosa.load(base_path, sr=TARGET_SAMPLE_RATE, mono=True)
        base_audio = np.asarray(base_audio, dtype=np.float64)
        artifact = load_conditioning_artifact(profile.conditioningArtifactPath)
        target_spectrum = np.array(artifact["average_spectrum"], dtype=np.float32)
        target_f0 = float(artifact.get("median_f0", 180.0))
        target_rms = float(artifact.get("average_rms", 0.12))

        base_f0 = librosa.yin(base_audio, fmin=75, fmax=350, sr=TARGET_SAMPLE_RATE, frame_length=1024, hop_length=256)
        valid_f0 = base_f0[np.isfinite(base_f0)]
        source_f0 = float(np.median(valid_f0)) if valid_f0.size else 180.0
        semitone_shift = 12 * math.log2(max(target_f0, 80.0) / max(source_f0, 80.0))
        if controls:
            semitone_shift += controls.pitch * 0.35
        semitone_shift = float(np.clip(semitone_shift, -8, 8))

        shifted = self._pitch_shift_resample(base_audio, semitone_shift)
        spectral = librosa.stft(shifted, n_fft=1024, hop_length=256)
        magnitude, phase = np.abs(spectral), np.angle(spectral)
        source_spectrum = np.mean(magnitude + 1e-6, axis=1)
        eq_ratio = np.clip(target_spectrum / np.maximum(source_spectrum, 1e-6), 0.6, 1.8)
        eq_ratio = np.sqrt(eq_ratio)[:, None]
        matched = magnitude * eq_ratio
        reconstructed = librosa.istft(matched * np.exp(1j * phase), hop_length=256, length=len(shifted))

        current_rms = float(np.sqrt(np.mean(reconstructed**2))) if reconstructed.size else 0.0
        gain = target_rms / max(current_rms, 1e-4)
        if controls:
            gain *= 0.92 + controls.intensity * 0.3
        conditioned = reconstructed * np.clip(gain, 0.7, 1.6)
        return normalize_audio(conditioned)

    def _pitch_shift_resample(self, audio: np.ndarray, semitone_shift: float) -> np.ndarray:
        factor = 2 ** (semitone_shift / 12.0)
        if abs(factor - 1.0) < 0.01:
            return audio
        pitched = signal.resample(audio, max(1, int(len(audio) / factor)))
        restored = signal.resample(pitched, len(audio))
        return np.asarray(restored, dtype=np.float64)


class XttsTtsProvider(TtsProvider):
    name = "xtts"
    label = "Coqui XTTS-v2"
    cloning_capable = True
    _shared_tts_by_device: dict[str, object] = {}

    def __init__(self) -> None:
        self._tts = None
        self._device = None

    def is_available(self) -> bool:
        return importlib.util.find_spec("TTS") is not None and self._tos_accepted()

    def unavailable_reason(self) -> str:
        if importlib.util.find_spec("TTS") is None:
            return "Python package 'TTS' is not installed."
        if not self._tos_accepted():
            return "Set COQUI_TOS_AGREED=1 after accepting the Coqui CPML terms for XTTS-v2."
        return ""

    def synthesize(self, text: str, profile: VoiceProfile, controls: SynthesisControls | None, output_path: Path) -> Path:
        if not self.is_available():
            raise RuntimeError(self.unavailable_reason())
        if not profile.samples:
            raise RuntimeError("XTTS requires at least one processed speaker sample.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tts = self._get_tts()
        speaker_wavs = [sample.processedPath for sample in profile.samples]
        language = infer_language(text)
        split_sentences = len(text) > 240
        kwargs = {
            "text": text,
            "file_path": str(output_path),
            "speaker_wav": speaker_wavs,
            "language": language,
            "split_sentences": split_sentences,
        }
        tts.tts_to_file(**kwargs)
        return output_path

    def _get_tts(self):
        if self._tts is not None:
            return self._tts
        self._patch_torch_load_for_xtts()
        self._patch_torchaudio_load_for_xtts()
        from TTS.api import TTS

        requested_device = _preferred_tts_device()
        candidates = _xtts_device_candidates(requested_device)
        errors: list[str] = []

        for device in candidates:
            shared = self.__class__._shared_tts_by_device.get(device)
            if shared is not None:
                self._tts = shared
                self._device = device
                return self._tts
            try:
                instance = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
                self.__class__._shared_tts_by_device[device] = instance
                self._tts = instance
                self._device = device
                return self._tts
            except Exception as exc:
                errors.append(f"{device}: {exc}")
                if device == "cuda":
                    continue
                raise

        raise RuntimeError("XTTS initialization failed. " + " | ".join(errors))

    def _tos_accepted(self) -> bool:
        return os.environ.get("COQUI_TOS_AGREED") == "1"

    def _patch_torch_load_for_xtts(self) -> None:
        import torch

        if getattr(torch.load, "_voice_studio_xtts_patch", False):
            return

        original_load = torch.load

        def patched_load(*args, **kwargs):
            kwargs.setdefault("weights_only", False)
            return original_load(*args, **kwargs)

        patched_load._voice_studio_xtts_patch = True  # type: ignore[attr-defined]
        torch.load = patched_load  # type: ignore[assignment]

    def _patch_torchaudio_load_for_xtts(self) -> None:
        import torch
        import torchaudio

        if getattr(torchaudio.load, "_voice_studio_xtts_patch", False):
            return

        def patched_load(filepath, *args, **kwargs):
            audio, sr = sf.read(filepath, dtype="float32", always_2d=True)
            tensor = torch.from_numpy(audio.T.copy())
            return tensor, sr

        patched_load._voice_studio_xtts_patch = True  # type: ignore[attr-defined]
        torchaudio.load = patched_load  # type: ignore[assignment]


class OpenVoiceTtsProvider(TtsProvider):
    name = "openvoice"
    label = "OpenVoice"
    cloning_capable = True

    def is_available(self) -> bool:
        return importlib.util.find_spec("openvoice") is not None

    def unavailable_reason(self) -> str:
        return "Python package/module 'openvoice' is not installed."

    def synthesize(self, text: str, profile: VoiceProfile, controls: SynthesisControls | None, output_path: Path) -> Path:
        raise RuntimeError("OpenVoice adapter is reserved for environments with OpenVoice installed and configured.")


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


def infer_language(text: str) -> str:
    return "en"


def _cuda_available() -> bool:
    with contextlib.suppress(Exception):
        import torch

        return bool(torch.cuda.is_available())
    return False


def _preferred_tts_device() -> str:
    requested = env_str("VOICE_STUDIO_DEVICE", "auto").strip().lower()
    if requested in {"cpu", "cuda", "auto"}:
        return requested
    return "auto"


def _xtts_device_candidates(requested: str) -> list[str]:
    if requested == "cpu":
        return ["cpu"]
    if requested == "cuda":
        return ["cuda", "cpu"]
    if _cuda_available():
        return ["cuda", "cpu"]
    return ["cpu"]


def probe_duration_seconds(input_path: str) -> float:
    ffprobe = resolve_ffprobe()
    if ffprobe:
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
        if result.returncode == 0:
            with contextlib.suppress(ValueError):
                return float(result.stdout.strip())
    with contextlib.suppress(Exception):
        return float(librosa.get_duration(path=input_path))
    return 10.0
