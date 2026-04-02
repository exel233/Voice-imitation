from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SynthesisControls(BaseModel):
    emotion: Literal["neutral", "warm", "excited", "serious", "sad", "calm", "energetic"] = "neutral"
    style: str = "natural"
    speakingRate: float = 1.0
    pitch: float = 0.0
    intensity: float = 0.5
    expressiveness: float = 0.5
    pauseScale: float = 1.0
    emphasis: list[str] = Field(default_factory=list)


class VoiceSampleRecord(BaseModel):
    id: str
    originalName: str
    rawPath: str
    processedPath: str
    format: str
    durationSec: float
    sampleRate: int
    channels: int
    warnings: list[str] = Field(default_factory=list)
    qualityScore: float = 0


class ProfileDiagnostics(BaseModel):
    qualityScore: float = 0
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    totalDurationSec: float = 0
    recommendedMinSec: float = 20


class VoiceProfile(BaseModel):
    id: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str
    sampleIds: list[str] = Field(default_factory=list)
    samples: list[VoiceSampleRecord] = Field(default_factory=list)
    previewAudioPath: str | None = None
    quickPreviewAudioPath: str | None = None
    conditioningArtifactPath: str | None = None
    authorizedUseConfirmed: bool = False
    status: Literal["processing", "ready", "low_quality", "failed"] = "processing"
    requestedProvider: str = "adaptive_clone"
    synthesisProvider: str = "fallback_generic"
    cloningCapable: bool = False
    fallbackReason: str | None = None
    diagnostics: ProfileDiagnostics = Field(default_factory=ProfileDiagnostics)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectRecord(BaseModel):
    id: str
    name: str
    kind: Literal["tts", "audioReplacement", "videoReplacement"]
    createdAt: str
    updatedAt: str
    profileId: str | None = None
    sourceMediaPath: str | None = None
    outputPath: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class JobRecord(BaseModel):
    id: str
    type: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"] = "queued"
    progress: float = 0
    step: str = "Queued"
    message: str = ""
    logs: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str
    projectId: str | None = None
    outputPath: str | None = None
    resultId: str | None = None


class AppSettings(BaseModel):
    backendUrl: str = "http://127.0.0.1:8765"
    device: Literal["cpu", "cuda", "auto"] = "auto"
    precision: Literal["fp32", "fp16", "int8"] = "fp32"
    storageRoot: str = "storage"
    enableDenoise: bool = True
    enableSourceSeparation: bool = True
    preferredTtsProvider: str = "xtts"
    preferredAsrProvider: str = "fallback"
    preferredVcProvider: str = "fallback"


class TranscriptSegment(BaseModel):
    id: str
    startSec: float
    endSec: float
    text: str
    speaker: str | None = None


class CreateVoiceProfileRequest(BaseModel):
    name: str
    description: str = ""
    samplePaths: list[str]
    authorizedUseConfirmed: bool = False


class UpdateProfileReferenceRequest(BaseModel):
    sampleIds: list[str] = Field(default_factory=list)
    excerptIds: list[str] = Field(default_factory=list)
    regeneratePreview: bool = False


class TtsRequest(BaseModel):
    text: str
    profileId: str
    controls: SynthesisControls
    projectName: str | None = None
    clientJobId: str | None = None


class ReplacementRequest(BaseModel):
    inputPath: str
    profileId: str
    controls: SynthesisControls
    clientJobId: str | None = None


class SegmentInspectionRequest(BaseModel):
    inputPath: str
