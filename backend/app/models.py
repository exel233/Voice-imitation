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


class VoiceProfile(BaseModel):
    id: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str
    sampleIds: list[str] = Field(default_factory=list)
    previewAudioPath: str | None = None
    authorizedUseConfirmed: bool = False
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


class AppSettings(BaseModel):
    backendUrl: str = "http://127.0.0.1:8765"
    device: Literal["cpu", "cuda", "auto"] = "auto"
    precision: Literal["fp32", "fp16", "int8"] = "fp32"
    storageRoot: str = "storage"
    enableDenoise: bool = True
    enableSourceSeparation: bool = True
    preferredTtsProvider: str = "fallback"
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


class TtsRequest(BaseModel):
    text: str
    profileId: str
    controls: SynthesisControls
    projectName: str | None = None


class ReplacementRequest(BaseModel):
    inputPath: str
    profileId: str
    controls: SynthesisControls


class SegmentInspectionRequest(BaseModel):
    inputPath: str
