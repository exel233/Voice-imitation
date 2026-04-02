from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from .media_tools import resolve_ffmpeg
from .models import ProfileDiagnostics, VoiceSampleRecord
from .storage import new_id, profile_artifacts_dir, profile_preview_dir, profile_processed_dir, profile_raw_dir

TARGET_SAMPLE_RATE = 24000
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}


def ingest_sample_from_path(profile_id: str, source_path: str) -> VoiceSampleRecord:
    source = Path(source_path)
    if source.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError(f"Unsupported audio format: {source.suffix}")
    if not source.exists():
        raise FileNotFoundError(f"Sample does not exist: {source}")

    sample_id = new_id("sample")
    raw_target = profile_raw_dir(profile_id) / f"{sample_id}{source.suffix.lower()}"
    shutil.copy2(source, raw_target)
    return preprocess_sample(profile_id, sample_id, raw_target, source.name)


def ingest_uploaded_bytes(profile_id: str, filename: str, payload: bytes) -> VoiceSampleRecord:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError(f"Unsupported audio format: {suffix}")
    sample_id, raw_target = stage_uploaded_bytes(profile_id, filename, payload)
    return preprocess_sample(profile_id, sample_id, raw_target, filename)


def stage_uploaded_bytes(profile_id: str, filename: str, payload: bytes) -> tuple[str, Path]:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError(f"Unsupported audio format: {suffix}")
    sample_id = new_id("sample")
    raw_target = profile_raw_dir(profile_id) / f"{sample_id}{suffix}"
    raw_target.write_bytes(payload)
    return sample_id, raw_target


def preprocess_sample(profile_id: str, sample_id: str, raw_path: Path, original_name: str) -> VoiceSampleRecord:
    audio, sr = load_audio_for_processing(raw_path)
    if audio.size == 0:
        raise ValueError("Uploaded sample is empty")

    trimmed, _ = librosa.effects.trim(audio, top_db=28)
    processed = normalize_audio(trimmed if trimmed.size else audio)
    processed_path = profile_processed_dir(profile_id) / f"{sample_id}.wav"
    sf.write(processed_path, processed, TARGET_SAMPLE_RATE)

    duration_sec = float(len(processed) / TARGET_SAMPLE_RATE)
    warnings = analyze_sample_warnings(processed, TARGET_SAMPLE_RATE)
    quality_score = score_sample_quality(processed, TARGET_SAMPLE_RATE, warnings)
    return VoiceSampleRecord(
        id=sample_id,
        originalName=original_name,
        rawPath=str(raw_path.resolve()),
        processedPath=str(processed_path.resolve()),
        format=raw_path.suffix.lower().lstrip("."),
        durationSec=duration_sec,
        sampleRate=TARGET_SAMPLE_RATE,
        channels=1,
        warnings=warnings,
        qualityScore=quality_score,
    )


def load_audio_for_processing(source_path: Path) -> tuple[np.ndarray, int]:
    try:
        audio, sr = librosa.load(source_path, sr=TARGET_SAMPLE_RATE, mono=True)
        return audio, sr
    except Exception as exc:
        ffmpeg = resolve_ffmpeg()
        if not ffmpeg:
            raise ValueError(
                f"Could not decode audio file '{source_path.name}'. Install FFmpeg or convert the sample to WAV/MP3 first."
            ) from exc

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        try:
            result = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(source_path),
                    "-ac",
                    "1",
                    "-ar",
                    str(TARGET_SAMPLE_RATE),
                    str(temp_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0 or not temp_path.exists():
                stderr = (result.stderr or "").strip().splitlines()
                detail = stderr[-1] if stderr else f"ffmpeg exited with code {result.returncode}"
                raise ValueError(f"Could not decode audio file '{source_path.name}': {detail}") from exc
            audio, sr = librosa.load(temp_path, sr=TARGET_SAMPLE_RATE, mono=True)
            return audio, sr
        finally:
            temp_path.unlink(missing_ok=True)


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(audio))) if audio.size else 0
    if peak > 0:
        audio = audio / peak * 0.92
    rms = float(np.sqrt(np.mean(audio**2))) if audio.size else 0
    if rms > 1e-4:
        audio = audio * min(1.0, 0.18 / rms)
    return np.clip(audio, -0.98, 0.98).astype(np.float32)


def analyze_sample_warnings(audio: np.ndarray, sample_rate: int) -> list[str]:
    warnings: list[str] = []
    duration_sec = len(audio) / sample_rate
    if duration_sec < 6:
        warnings.append("Sample is very short. Use 20-60 seconds of clean speech for stronger speaker similarity.")
    silence_ratio = float(np.mean(np.abs(audio) < 0.01))
    if silence_ratio > 0.45:
        warnings.append("Sample contains a lot of silence. Trim leading and trailing silence for better cloning.")
    clipping_ratio = float(np.mean(np.abs(audio) > 0.97))
    if clipping_ratio > 0.005:
        warnings.append("Sample appears clipped or distorted.")
    centroid = librosa.feature.spectral_centroid(y=audio, sr=sample_rate)
    if float(np.mean(centroid)) < 900:
        warnings.append("Sample sounds muffled or low-bandwidth, which may weaken similarity.")
    zcr = librosa.feature.zero_crossing_rate(y=audio)
    if float(np.mean(zcr)) > 0.18:
        warnings.append("Sample may be noisy or contain strong background texture.")
    return warnings


def score_sample_quality(audio: np.ndarray, sample_rate: int, warnings: list[str]) -> float:
    duration_sec = len(audio) / sample_rate
    score = min(1.0, duration_sec / 30.0)
    silence_ratio = float(np.mean(np.abs(audio) < 0.01))
    voiced_ratio = max(0.0, 1.0 - silence_ratio)
    score = min(1.0, score * (0.55 + 0.45 * voiced_ratio))
    if warnings:
        score -= min(0.4, 0.08 * len(set(warnings)))
    return round(max(0.05, min(1.0, score)), 3)


def build_profile_artifacts(profile_id: str, samples: list[VoiceSampleRecord]) -> tuple[str, ProfileDiagnostics]:
    spectra: list[np.ndarray] = []
    f0_values: list[float] = []
    rms_values: list[float] = []
    mfcc_vectors: list[np.ndarray] = []
    durations = 0.0
    warnings: list[str] = []

    for sample in samples:
        audio, sr = librosa.load(sample.processedPath, sr=TARGET_SAMPLE_RATE, mono=True)
        durations += sample.durationSec
        warnings.extend(sample.warnings)

        stft = np.abs(librosa.stft(audio, n_fft=1024, hop_length=256))
        spectra.append(np.mean(stft + 1e-6, axis=1))
        rms_values.append(float(np.sqrt(np.mean(audio**2))))
        mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
        mfcc_vectors.append(np.mean(mfcc, axis=1))
        f0 = librosa.yin(audio, fmin=75, fmax=350, sr=sr, frame_length=1024, hop_length=256)
        valid_f0 = f0[np.isfinite(f0)]
        if valid_f0.size:
            f0_values.extend(valid_f0.tolist())

    avg_spectrum = np.mean(np.vstack(spectra), axis=0) if spectra else np.ones(513, dtype=np.float32)
    avg_mfcc = np.mean(np.vstack(mfcc_vectors), axis=0) if mfcc_vectors else np.zeros(13, dtype=np.float32)
    median_f0 = float(np.median(f0_values)) if f0_values else 180.0
    avg_rms = float(np.mean(rms_values)) if rms_values else 0.12

    quality_score = min(1.0, max(0.0, durations / 30.0))
    if len(samples) > 1:
        quality_score = min(1.0, quality_score + 0.1)
    if warnings:
        quality_score = max(0.15, quality_score - min(0.35, len(set(warnings)) * 0.05))

    diagnostics = ProfileDiagnostics(
        qualityScore=round(quality_score, 3),
        warnings=sorted(set(warnings)),
        notes=[
            "Profile conditioning assets were built from processed uploaded samples.",
            "Current default backend uses adaptive timbre matching, not a full neural zero-shot cloner.",
        ],
        totalDurationSec=round(durations, 2),
        recommendedMinSec=20,
    )

    artifact_path = profile_artifacts_dir(profile_id) / "conditioning.json"
    artifact_path.write_text(
        json.dumps(
            {
                "target_sample_rate": TARGET_SAMPLE_RATE,
                "average_spectrum": avg_spectrum.tolist(),
                "average_mfcc": avg_mfcc.tolist(),
                "median_f0": median_f0,
                "average_rms": avg_rms,
                "sample_count": len(samples),
                "total_duration_sec": durations,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return str(artifact_path.resolve()), diagnostics


def build_xtts_reference(
    profile_id: str,
    samples: list[VoiceSampleRecord],
    target_seconds: float = 28.0,
    preferred_sample_ids: list[str] | None = None,
    preferred_excerpt_ids: list[str] | None = None,
) -> str | None:
    selected_audio: list[np.ndarray] = []
    excerpt_manifest = build_xtts_reference_excerpts(profile_id, samples, preferred_sample_ids=preferred_sample_ids)
    preferred_excerpt_set = set(preferred_excerpt_ids or [])
    ordered_excerpts = sorted(
        excerpt_manifest,
        key=lambda excerpt: (
            excerpt["id"] in preferred_excerpt_set,
            excerpt["sampleId"] in set(preferred_sample_ids or []),
            excerpt["score"],
            excerpt["durationSec"],
        ),
        reverse=True,
    )

    total_selected = 0.0
    bridge = np.zeros(int(0.12 * TARGET_SAMPLE_RATE), dtype=np.float32)
    for excerpt in ordered_excerpts:
        if preferred_excerpt_set and excerpt["id"] not in preferred_excerpt_set:
            continue
        audio, _ = librosa.load(excerpt["path"], sr=TARGET_SAMPLE_RATE, mono=True)
        if audio.size == 0:
            continue
        selected_audio.append(audio.astype(np.float32))
        total_selected += len(audio) / TARGET_SAMPLE_RATE
        if total_selected >= target_seconds:
            break

    if not selected_audio:
        return None

    combined_parts: list[np.ndarray] = []
    for index, chunk in enumerate(selected_audio):
        if index > 0:
            combined_parts.append(bridge)
        combined_parts.append(chunk)

    combined = normalize_audio(np.concatenate(combined_parts))
    reference_path = profile_artifacts_dir(profile_id) / "xtts_reference.wav"
    sf.write(reference_path, combined, TARGET_SAMPLE_RATE)
    return str(reference_path.resolve())

def build_xtts_reference_excerpts(
    profile_id: str,
    samples: list[VoiceSampleRecord],
    *,
    preferred_sample_ids: list[str] | None = None,
) -> list[dict]:
    excerpt_dir = profile_artifacts_dir(profile_id) / "reference_excerpts"
    excerpt_dir.mkdir(parents=True, exist_ok=True)
    for stale in excerpt_dir.glob("*.wav"):
        stale.unlink(missing_ok=True)

    preferred_set = set(preferred_sample_ids or [])
    ranked_samples = sorted(
        samples,
        key=lambda sample: (sample.id in preferred_set, sample.qualityScore, sample.durationSec),
        reverse=True,
    )
    max_per_sample = min(12.0, max(6.0, 28.0 / max(len(ranked_samples), 1)))
    excerpt_manifest: list[dict] = []

    for sample in ranked_samples:
        audio, _ = librosa.load(sample.processedPath, sr=TARGET_SAMPLE_RATE, mono=True)
        excerpt_specs = extract_reference_excerpts(audio, TARGET_SAMPLE_RATE, max_duration=max_per_sample)
        for index, excerpt in enumerate(excerpt_specs, start=1):
            excerpt_id = new_id("excerpt")
            excerpt_path = excerpt_dir / f"{excerpt_id}.wav"
            sf.write(excerpt_path, excerpt["audio"], TARGET_SAMPLE_RATE)
            excerpt_manifest.append(
                {
                    "id": excerpt_id,
                    "sampleId": sample.id,
                    "originalName": sample.originalName,
                    "path": str(excerpt_path.resolve()),
                    "durationSec": round(excerpt["durationSec"], 2),
                    "score": round(excerpt["score"], 3),
                    "startSec": round(excerpt["startSec"], 2),
                    "endSec": round(excerpt["endSec"], 2),
                    "label": f"{sample.originalName} excerpt {index}",
                }
            )

    manifest_path = profile_artifacts_dir(profile_id) / "xtts_reference_excerpts.json"
    manifest_path.write_text(json.dumps(excerpt_manifest, indent=2), encoding="utf-8")
    return excerpt_manifest


def extract_reference_excerpts(audio: np.ndarray, sample_rate: int, max_duration: float = 12.0) -> list[dict]:
    intervals = librosa.effects.split(audio, top_db=30, frame_length=2048, hop_length=256)
    candidates: list[dict] = []

    for start, end in intervals:
        segment = audio[start:end]
        duration = len(segment) / sample_rate
        if duration < 1.0:
            continue
        if duration > 8.0:
            middle = len(segment) // 2
            half = int(4.0 * sample_rate)
            clip_start = max(0, middle - half)
            clip_end = min(len(segment), middle + half)
            segment = segment[clip_start:clip_end]
            start = start + clip_start
            end = start + len(segment)
            duration = len(segment) / sample_rate
        rms = float(np.sqrt(np.mean(segment**2))) if segment.size else 0.0
        silence_ratio = float(np.mean(np.abs(segment) < 0.01))
        clipping_ratio = float(np.mean(np.abs(segment) > 0.97))
        score = (duration * 0.4) + (rms * 4.5) + ((1.0 - silence_ratio) * 1.2) - (clipping_ratio * 12.0)
        candidates.append(
            {
                "score": score,
                "audio": segment.astype(np.float32),
                "durationSec": duration,
                "startSec": start / sample_rate,
                "endSec": end / sample_rate,
            }
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)

    chosen: list[dict] = []
    total = 0.0
    for candidate in candidates:
        seg_duration = candidate["durationSec"]
        if total + seg_duration > max_duration and total >= 6.0:
            continue
        chosen.append(candidate)
        total += seg_duration
        if total >= max_duration:
            break

    if not chosen and audio.size:
        fallback_duration = min(max_duration, len(audio) / sample_rate)
        fallback = audio[: int(fallback_duration * sample_rate)]
        if fallback.size:
            chosen.append(
                {
                    "score": max(0.1, fallback_duration * 0.3),
                    "audio": fallback.astype(np.float32),
                    "durationSec": fallback_duration,
                    "startSec": 0.0,
                    "endSec": fallback_duration,
                }
            )
    return chosen


def load_conditioning_artifact(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def synthesize_quick_profile_preview(profile_id: str, provider, profile, text: str) -> str | None:
    preview_path = profile_preview_dir(profile_id) / "quick_preview.wav"
    provider.synthesize(text=text, profile=profile, controls=None, output_path=preview_path)
    return str(preview_path.resolve()) if preview_path.exists() else None


def create_media_preview_excerpt(profile_id: str, sample: VoiceSampleRecord, seconds: float = 6) -> str:
    audio, sr = librosa.load(sample.processedPath, sr=TARGET_SAMPLE_RATE, mono=True)
    excerpt = audio[: int(seconds * sr)]
    path = profile_preview_dir(profile_id) / f"{sample.id}_excerpt.wav"
    sf.write(path, excerpt, sr)
    return str(path.resolve())


def generate_solid_color_video(audio_path: str, output_path: str, ffmpeg_path: str) -> None:
    subprocess.run(
        [
            ffmpeg_path,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=0xefe6d7:s=1280x720:d=8",
            "-i",
            audio_path,
            "-shortest",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            output_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
