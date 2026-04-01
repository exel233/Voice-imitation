from __future__ import annotations

import contextlib
import importlib.util
import shutil
from pathlib import Path


def resolve_ffmpeg() -> str | None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg

    if importlib.util.find_spec("imageio_ffmpeg") is None:
        return None

    with contextlib.suppress(Exception):
        import imageio_ffmpeg

        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and Path(path).exists():
            return path
    return None


def resolve_ffprobe() -> str | None:
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        return ffprobe

    ffmpeg = resolve_ffmpeg()
    if not ffmpeg:
        return None

    ffmpeg_path = Path(ffmpeg)
    candidates = [
        ffmpeg_path.with_name("ffprobe.exe"),
        ffmpeg_path.with_name("ffprobe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None
