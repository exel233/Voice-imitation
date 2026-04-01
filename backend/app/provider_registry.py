from __future__ import annotations

from dataclasses import dataclass

from .providers import AdaptiveCloneTtsProvider, AsrProvider, FallbackAsrProvider, GenericFallbackTtsProvider, OpenVoiceTtsProvider, TtsProvider, XttsTtsProvider


@dataclass(frozen=True)
class ProviderRecommendation:
    key: str
    category: str
    quality_note: str
    install_note: str
    cloning_capable: bool


TTS_RECOMMENDATIONS = [
    ProviderRecommendation("xtts", "tts", "Neural zero-shot cloning with speaker_wav references via Coqui XTTS-v2", "Install Coqui TTS package and model dependencies", True),
    ProviderRecommendation("openvoice", "tts", "OpenVoice adapter slot for future tone-color conversion pipeline", "Install OpenVoice runtime and checkpoints", True),
    ProviderRecommendation("adaptive_clone", "tts", "Lightweight local fallback that adapts timbre from uploaded samples", "Included by default", True),
    ProviderRecommendation("fallback_generic", "tts", "Generic TTS only. Does not clone speaker identity.", "Included by default", False),
]

ASR_RECOMMENDATIONS = [
    ProviderRecommendation("fallback", "asr", "Placeholder segmentation only", "Included by default", False),
    ProviderRecommendation("faster-whisper", "asr", "Strong practical local ASR baseline", "Install faster-whisper adapter", False),
]


def get_tts_provider_chain(preferred: str) -> list[TtsProvider]:
    ordered = [preferred] + [key for key in ["xtts", "openvoice", "adaptive_clone", "fallback_generic"] if key != preferred]
    providers: list[TtsProvider] = []
    for key in ordered:
        providers.append(_instantiate_tts_provider(key))
    return providers


def resolve_tts_provider(preferred: str) -> tuple[TtsProvider, str | None]:
    failure_reasons: list[str] = []
    for provider in get_tts_provider_chain(preferred):
        if provider.is_available():
            if failure_reasons:
                return provider, "; ".join(failure_reasons)
            return provider, None
        failure_reasons.append(f"{provider.name} unavailable: {provider.unavailable_reason()}")
    provider = GenericFallbackTtsProvider()
    return provider, "; ".join(failure_reasons)


def _instantiate_tts_provider(name: str) -> TtsProvider:
    if name == "xtts":
        return XttsTtsProvider()
    if name == "openvoice":
        return OpenVoiceTtsProvider()
    if name == "fallback_generic":
        return GenericFallbackTtsProvider()
    return AdaptiveCloneTtsProvider()


def resolve_asr_provider(name: str) -> AsrProvider:
    return FallbackAsrProvider()
