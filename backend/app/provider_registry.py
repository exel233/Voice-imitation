from __future__ import annotations

from dataclasses import dataclass

from .providers import AsrProvider, FallbackAsrProvider, FallbackTtsProvider, TtsProvider


@dataclass(frozen=True)
class ProviderRecommendation:
    key: str
    category: str
    quality_note: str
    install_note: str


TTS_RECOMMENDATIONS = [
    ProviderRecommendation("fallback", "tts", "Runnable baseline only", "Included by default"),
    ProviderRecommendation("xtts", "tts", "Strong zero-shot cloning baseline", "Install XTTS-v2 backend adapter"),
    ProviderRecommendation("styletts2", "tts", "High expressiveness potential", "Install StyleTTS2 backend adapter"),
    ProviderRecommendation("f5tts", "tts", "Strong controllable speech generation candidate", "Install F5-TTS backend adapter"),
]

ASR_RECOMMENDATIONS = [
    ProviderRecommendation("fallback", "asr", "Placeholder segmentation only", "Included by default"),
    ProviderRecommendation("faster-whisper", "asr", "Strong practical local ASR baseline", "Install faster-whisper adapter"),
]


def resolve_tts_provider(name: str) -> TtsProvider:
    # Future providers should be swapped here without changing service callers.
    return FallbackTtsProvider()


def resolve_asr_provider(name: str) -> AsrProvider:
    # Future providers should be swapped here without changing service callers.
    return FallbackAsrProvider()
