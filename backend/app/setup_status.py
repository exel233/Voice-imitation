from __future__ import annotations

import importlib.util

from .models import AppSettings
from .media_tools import resolve_ffmpeg, resolve_ffprobe
from .provider_registry import resolve_tts_provider
from .storage import load_settings


def get_setup_status() -> dict:
    settings: AppSettings = load_settings()
    requested = settings.preferredTtsProvider
    provider, note = resolve_tts_provider(requested)

    xtts_importable = importlib.util.find_spec("TTS") is not None
    openvoice_importable = importlib.util.find_spec("openvoice") is not None
    ffmpeg_available = resolve_ffmpeg() is not None
    ffprobe_available = resolve_ffprobe() is not None

    return {
        "requestedTtsProvider": requested,
        "activeTtsProvider": provider.name,
        "providerResolutionNote": note,
        "xtts": {
            "importable": xtts_importable,
            "available": provider.name == "xtts",
            "needsTosAcceptance": xtts_importable and provider.name != "xtts" and requested == "xtts",
        },
        "openvoice": {
            "importable": openvoice_importable,
            "available": provider.name == "openvoice",
        },
        "mediaTools": {
            "ffmpeg": ffmpeg_available,
            "ffprobe": ffprobe_available,
        },
    }
