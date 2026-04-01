from __future__ import annotations

import contextlib
import shutil
import subprocess
from pathlib import Path

from .models import AppSettings, CreateVoiceProfileRequest, JobRecord, ProjectRecord, ReplacementRequest, TtsRequest, VoiceProfile
from .provider_registry import resolve_asr_provider, resolve_tts_provider
from .storage import CACHE, OUTPUTS, copy_to_profile_sample_area, load_settings, new_id, now_iso, read_profile, save_job, save_profile, save_project


class VoiceProfileService:
    def create_profile(self, request: CreateVoiceProfileRequest) -> VoiceProfile:
        profile_id = new_id("profile")
        samples = [copy_to_profile_sample_area(profile_id, source_path) for source_path in request.samplePaths]
        timestamp = now_iso()
        profile = VoiceProfile(
            id=profile_id,
            name=request.name,
            description=request.description,
            createdAt=timestamp,
            updatedAt=timestamp,
            sampleIds=[new_id("sample") for _ in samples],
            previewAudioPath=samples[0] if samples else None,
            authorizedUseConfirmed=request.authorizedUseConfirmed,
            metadata={
                "sourceSamples": samples,
                "recommendedQualityNote": "Swap in XTTS/OpenVoice/F5-TTS providers for stronger quality and controllability.",
            },
        )
        return save_profile(profile)


class ProjectService:
    def create(self, *, name: str, kind: str, profile_id: str | None = None, source_media_path: str | None = None, settings: dict | None = None) -> ProjectRecord:
        timestamp = now_iso()
        project = ProjectRecord(
            id=new_id("project"),
            name=name,
            kind=kind,
            createdAt=timestamp,
            updatedAt=timestamp,
            profileId=profile_id,
            sourceMediaPath=source_media_path,
            settings=settings or {},
        )
        return save_project(project)

    def finalize(self, project: ProjectRecord, output_path: str) -> ProjectRecord:
        updated = project.model_copy(update={"updatedAt": now_iso(), "outputPath": output_path})
        return save_project(updated)


class JobService:
    def create(self, job_type: str, project_id: str | None = None) -> JobRecord:
        timestamp = now_iso()
        return save_job(JobRecord(id=new_id("job"), type=job_type, createdAt=timestamp, updatedAt=timestamp, projectId=project_id))

    def update(self, job: JobRecord, **changes) -> JobRecord:
        return save_job(job.model_copy(update={"updatedAt": now_iso(), **changes}))


class SegmentService:
    def __init__(self) -> None:
        self.provider = resolve_asr_provider(load_settings().preferredAsrProvider)

    def inspect(self, input_path: str):
        return self.provider.transcribe_segments(input_path)


class TtsService:
    def __init__(self) -> None:
        self.provider = resolve_tts_provider(load_settings().preferredTtsProvider)
        self.projects = ProjectService()
        self.jobs = JobService()

    def synthesize(self, request: TtsRequest) -> JobRecord:
        profile = read_profile(request.profileId)
        project = self.projects.create(
            name=request.projectName or f"TTS - {profile.name}",
            kind="tts",
            profile_id=profile.id,
            settings=request.controls.model_dump(),
        )
        job = self.jobs.create("tts.synthesize", project.id)
        job = self.jobs.update(job, status="running", progress=0.2, step="Preparing synthesis")
        output_path = OUTPUTS / f"{project.id}.wav"
        self.provider.synthesize(request.text, profile, request.controls, output_path)
        project = self.projects.finalize(project, str(output_path.resolve()))
        return self.jobs.update(job, status="completed", progress=1, step="Completed", message="Synthesis complete", outputPath=project.outputPath)


class ReplacementService:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.tts = resolve_tts_provider(load_settings().preferredTtsProvider)
        self.projects = ProjectService()
        self.jobs = JobService()
        self.segments = SegmentService()

    def process(self, request: ReplacementRequest) -> JobRecord:
        profile = read_profile(request.profileId)
        project = self.projects.create(
            name=f"{self.kind.title()} Replacement - {Path(request.inputPath).stem}",
            kind="audioReplacement" if self.kind == "audio" else "videoReplacement",
            profile_id=profile.id,
            source_media_path=request.inputPath,
            settings=request.controls.model_dump(),
        )
        job = self.jobs.create(f"{self.kind}.replacement", project.id)
        job = self.jobs.update(job, status="running", progress=0.15, step="Inspecting segments")
        transcript_segments = self.segments.inspect(request.inputPath)
        combined_text = " ".join(segment.text for segment in transcript_segments)
        temp_audio = CACHE / f"{project.id}_replacement.wav"
        self.tts.synthesize(combined_text, profile, request.controls, temp_audio)
        job = self.jobs.update(job, progress=0.65, step="Rendering output")
        output = self._render_media(request.inputPath, temp_audio, project.id)
        project = self.projects.finalize(project, str(output.resolve()))
        return self.jobs.update(job, status="completed", progress=1, step="Completed", message=f"{self.kind.title()} replacement complete", outputPath=project.outputPath)

    def _render_media(self, input_path: str, replacement_audio: Path, project_id: str) -> Path:
        ffmpeg = shutil.which("ffmpeg")
        source = Path(input_path)
        output = OUTPUTS / f"{project_id}{source.suffix if self.kind == 'video' else '.wav'}"
        output.parent.mkdir(parents=True, exist_ok=True)
        if not ffmpeg:
          if self.kind == "video":
              shutil.copy2(source, output)
          else:
              shutil.copy2(replacement_audio, output)
          return output
        if self.kind == "audio":
            command = [ffmpeg, "-y", "-i", str(replacement_audio), str(output)]
        else:
            command = [
                ffmpeg,
                "-y",
                "-i",
                input_path,
                "-i",
                str(replacement_audio),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-shortest",
                str(output),
            ]
        subprocess.run(command, capture_output=True, text=True, check=False)
        if not output.exists():
            with contextlib.suppress(Exception):
                shutil.copy2(source if self.kind == "video" else replacement_audio, output)
        return output


def get_settings() -> AppSettings:
    return load_settings()
