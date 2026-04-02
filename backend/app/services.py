from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from .audio_pipeline import (
    build_profile_artifacts,
    build_xtts_reference,
    build_xtts_reference_excerpts,
    create_media_preview_excerpt,
    ingest_sample_from_path,
    ingest_uploaded_bytes,
    stage_uploaded_bytes,
    synthesize_quick_profile_preview,
)
from .media_tools import resolve_ffmpeg
from .models import AppSettings, CreateVoiceProfileRequest, JobRecord, ProjectRecord, ReplacementRequest, TtsRequest, UpdateProfileReferenceRequest, VoiceProfile
from .provider_registry import resolve_asr_provider, resolve_tts_provider
from .storage import CACHE, OUTPUTS, load_settings, new_id, now_iso, profile_artifacts_dir, read_job, read_profile, save_job, save_profile, save_project

PROFILE_PREVIEW_TEXT = "This preview checks whether the saved profile is shaping the generated voice."


class VoiceProfileService:
    def __init__(self) -> None:
        settings = load_settings()
        self.requested_provider = settings.preferredTtsProvider
        self.provider, self.provider_resolution_note = resolve_tts_provider(settings.preferredTtsProvider)
        self.jobs = JobService()

    def create_profile_from_paths(self, request: CreateVoiceProfileRequest) -> VoiceProfile:
        profile_id = new_id("profile")
        job = self.jobs.create("voice_profile.build")
        try:
            self.jobs.update(job, status="running", progress=0.05, step="Validating samples", message="Checking source files")
            samples = []
            total = max(len(request.samplePaths), 1)
            for index, source_path in enumerate(request.samplePaths, start=1):
                samples.append(ingest_sample_from_path(profile_id, source_path))
                job = self.jobs.update(
                    job,
                    progress=0.15 + (0.35 * index / total),
                    step="Preprocessing samples",
                    message=f"Processed sample {index} of {total}",
                )
            profile = self._finalize_profile(profile_id, request.name, request.description, request.authorizedUseConfirmed, samples, job)
            self.jobs.update(job, status="completed", progress=1, step="Completed", message=f"Profile ready: {profile.name}")
            return profile
        except Exception as exc:
            self.jobs.update(job, status="failed", progress=1, step="Failed", message=str(exc))
            raise

    def create_profile_from_uploads(
        self,
        *,
        name: str,
        description: str,
        authorized: bool,
        files: list[tuple[str, bytes]],
        client_job_id: str | None = None,
    ) -> JobRecord:
        profile_id = new_id("profile")
        job = self.jobs.create("voice_profile.build", client_job_id=client_job_id)
        timestamp = now_iso()
        placeholder = VoiceProfile(
            id=profile_id,
            name=name,
            description=description,
            createdAt=timestamp,
            updatedAt=timestamp,
            authorizedUseConfirmed=authorized,
            status="processing",
            requestedProvider=self.requested_provider,
            synthesisProvider=self.provider.name,
            cloningCapable=self.provider.cloning_capable,
            fallbackReason=self.provider_resolution_note,
            metadata={"profileBuilder": "audio_preprocessing -> speaker_profile_builder -> speaker_profile_store"},
        )
        save_profile(placeholder)
        job = self.jobs.update(
            job,
            status="running",
            progress=0.05,
            step="Receiving upload",
            message="Upload received, building profile in background",
            resultId=profile_id,
        )

        manifest = {"samples": []}
        for filename, payload in files:
            sample_id, raw_path = stage_uploaded_bytes(profile_id, filename, payload)
            manifest["samples"].append(
                {
                    "sampleId": sample_id,
                    "originalName": filename,
                    "rawPath": str(raw_path.resolve()),
                }
            )
        manifest_path = profile_artifacts_dir(profile_id) / "upload_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "backend.app.profile_build_worker",
                "--profile-id",
                profile_id,
                "--job-id",
                job.id,
                "--name",
                name,
                "--description",
                description,
                *(["--authorized"] if authorized else []),
            ],
            cwd=str(Path(__file__).resolve().parents[2]),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return job

    def _finalize_profile(
        self,
        profile_id: str,
        name: str,
        description: str,
        authorized: bool,
        samples,
        job: JobRecord | None = None,
        *,
        generate_quick_preview: bool = True,
    ) -> VoiceProfile:
        timestamp = now_iso()
        if job:
            self.jobs.update(job, progress=0.62, step="Building conditioning assets", message="Computing reusable speaker profile artifacts")
        artifact_path, diagnostics = build_profile_artifacts(profile_id, samples)
        base_status = "ready" if diagnostics.qualityScore >= 0.45 else "low_quality"
        fallback_reason = self.provider_resolution_note
        if not self.provider.cloning_capable:
            base_status = "low_quality"
            fallback_reason = fallback_reason or "Current provider is generic fallback and does not truly clone speaker identity."
        diagnostics = diagnostics.model_copy(
            update={
                "notes": [
                    "Profile conditioning assets were built from processed uploaded samples.",
                    (
                        f"Neural speaker-conditioned synthesis is active through {self.provider.label}."
                        if self.provider.name in {"xtts", "openvoice"}
                        else "Current default backend uses adaptive timbre matching, not a full neural zero-shot cloner."
                    ),
                ]
            }
        )

        profile = VoiceProfile(
            id=profile_id,
            name=name,
            description=description,
            createdAt=timestamp,
            updatedAt=timestamp,
            sampleIds=[sample.id for sample in samples],
            samples=samples,
            previewAudioPath=create_media_preview_excerpt(profile_id, samples[0]) if samples else None,
            conditioningArtifactPath=artifact_path,
            authorizedUseConfirmed=authorized,
            status=base_status,
            requestedProvider=self.requested_provider,
            synthesisProvider=self.provider.name,
            cloningCapable=self.provider.cloning_capable,
            fallbackReason=fallback_reason,
            diagnostics=diagnostics,
            metadata={
                "sourceSamples": [sample.rawPath for sample in samples],
                "processedSamples": [sample.processedPath for sample in samples],
                "profileBuilder": "audio_preprocessing -> speaker_profile_builder -> speaker_profile_store",
            },
        )
        if self.provider.name == "xtts":
            excerpt_manifest = build_xtts_reference_excerpts(profile_id, samples)
            reference_path = build_xtts_reference(profile_id, samples)
            if reference_path:
                profile.metadata["xttsReferencePath"] = reference_path
                profile.metadata["xttsReferenceSampleIds"] = [
                    sample.id for sample in sorted(samples, key=lambda sample: (sample.qualityScore, sample.durationSec), reverse=True)
                ]
                profile.metadata["xttsReferenceExcerpts"] = excerpt_manifest
                profile.metadata["xttsReferenceExcerptIds"] = [excerpt["id"] for excerpt in excerpt_manifest[: min(len(excerpt_manifest), 4)]]
                profile.diagnostics = profile.diagnostics.model_copy(
                    update={
                        "notes": [
                            *profile.diagnostics.notes,
                            "XTTS uses a curated reference track built from the cleanest voiced excerpts instead of the full raw sample set.",
                        ]
                    }
                )
        if generate_quick_preview:
            if job:
                self.jobs.update(job, progress=0.82, step="Rendering preview", message="Generating quick profile preview")
            profile.quickPreviewAudioPath = synthesize_quick_profile_preview(profile_id, self.provider, profile, PROFILE_PREVIEW_TEXT)
        else:
            profile.diagnostics = profile.diagnostics.model_copy(
                update={
                    "notes": [
                        *profile.diagnostics.notes,
                        "Quick XTTS preview is deferred so profile creation completes faster on CPU.",
                    ]
                }
            )
        return save_profile(profile)

    def update_reference(self, profile_id: str, request: UpdateProfileReferenceRequest) -> VoiceProfile:
        profile = read_profile(profile_id)
        if not profile.samples:
            raise ValueError("Profile has no processed samples to curate.")
        if profile.synthesisProvider != "xtts":
            raise ValueError("Manual reference curation is currently available for XTTS profiles only.")

        selected_ids = request.sampleIds or [sample.id for sample in profile.samples]
        valid_ids = {sample.id for sample in profile.samples}
        curated_ids = [sample_id for sample_id in selected_ids if sample_id in valid_ids]
        if not curated_ids:
            raise ValueError("Choose at least one valid source sample for the XTTS reference.")

        excerpt_manifest = build_xtts_reference_excerpts(profile.id, profile.samples, preferred_sample_ids=curated_ids)
        valid_excerpt_ids = {excerpt["id"] for excerpt in excerpt_manifest}
        curated_excerpt_ids = [excerpt_id for excerpt_id in request.excerptIds if excerpt_id in valid_excerpt_ids]
        if not curated_excerpt_ids:
            curated_excerpt_ids = [excerpt["id"] for excerpt in excerpt_manifest[: min(len(excerpt_manifest), 4)]]

        reference_path = build_xtts_reference(
            profile.id,
            profile.samples,
            preferred_sample_ids=curated_ids,
            preferred_excerpt_ids=curated_excerpt_ids,
        )
        if not reference_path:
            raise ValueError("Could not build a curated XTTS reference from the selected samples.")

        notes = [note for note in profile.diagnostics.notes if "curated reference track" not in note.lower()]
        notes.append("XTTS uses a curated reference track built from your selected source samples and voiced excerpts.")

        updated = profile.model_copy(
            update={
                "updatedAt": now_iso(),
                "metadata": {
                    **profile.metadata,
                    "xttsReferencePath": reference_path,
                    "xttsReferenceSampleIds": curated_ids,
                    "xttsReferenceExcerpts": excerpt_manifest,
                    "xttsReferenceExcerptIds": curated_excerpt_ids,
                },
                "diagnostics": profile.diagnostics.model_copy(update={"notes": notes}),
            }
        )
        if request.regeneratePreview:
            updated.quickPreviewAudioPath = synthesize_quick_profile_preview(profile.id, self.provider, updated, PROFILE_PREVIEW_TEXT)
        return save_profile(updated)


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
    def create(self, job_type: str, project_id: str | None = None, client_job_id: str | None = None) -> JobRecord:
        timestamp = now_iso()
        return save_job(JobRecord(id=client_job_id or new_id("job"), type=job_type, createdAt=timestamp, updatedAt=timestamp, projectId=project_id))

    def update(self, job: JobRecord, **changes) -> JobRecord:
        logs = changes.pop("append_logs", None)
        current_logs = list(job.logs)
        if logs:
            current_logs.extend(logs)
        return save_job(job.model_copy(update={"updatedAt": now_iso(), "logs": current_logs, **changes}))

    def get(self, job_id: str) -> JobRecord:
        return read_job(job_id)



class SegmentService:
    def __init__(self) -> None:
        self.provider = resolve_asr_provider(load_settings().preferredAsrProvider)

    def inspect(self, input_path: str):
        return self.provider.transcribe_segments(input_path)


class TtsService:
    def __init__(self) -> None:
        settings = load_settings()
        self.requested_provider = settings.preferredTtsProvider
        self.provider, self.provider_resolution_note = resolve_tts_provider(settings.preferredTtsProvider)
        self.projects = ProjectService()
        self.jobs = JobService()

    def synthesize(self, request: TtsRequest) -> JobRecord:
        profile = read_profile(request.profileId)
        if (
            profile.synthesisProvider != self.provider.name
            or profile.cloningCapable != self.provider.cloning_capable
            or profile.fallbackReason != self.provider_resolution_note
        ):
            profile = save_profile(
                profile.model_copy(
                    update={
                        "updatedAt": now_iso(),
                        "requestedProvider": self.requested_provider,
                        "synthesisProvider": self.provider.name,
                        "cloningCapable": self.provider.cloning_capable,
                        "fallbackReason": self.provider_resolution_note,
                    }
                )
            )
        project = self.projects.create(
            name=request.projectName or f"TTS - {profile.name}",
            kind="tts",
            profile_id=profile.id,
            settings={**request.controls.model_dump(), "provider": self.provider.name},
        )
        job = self.jobs.create("tts.synthesize", project.id, client_job_id=request.clientJobId)
        job = self.jobs.update(
            job,
            status="running",
            progress=0.2,
            step="Preparing speaker-conditioned synthesis",
            append_logs=[
                f"Requested provider: {self.requested_provider}",
                f"Actual provider: {self.provider.name}",
                f"Cloning capable: {self.provider.cloning_capable}",
                *([f"Resolution note: {self.provider_resolution_note}"] if self.provider_resolution_note else []),
            ],
        )
        output_path = OUTPUTS / f"{project.id}.wav"
        job = self.jobs.update(job, progress=0.45, step="Running synthesis", message="Generating speech audio")
        self.provider.synthesize(request.text, profile, request.controls, output_path)
        job = self.jobs.update(job, progress=0.85, step="Finalizing output", message="Saving generated audio")
        project = self.projects.finalize(project, str(output_path.resolve()))
        label = "Speaker-conditioned synthesis complete" if self.provider.cloning_capable else "Generic fallback synthesis complete"
        return self.jobs.update(job, status="completed", progress=1, step="Completed", message=label, outputPath=project.outputPath)


class ReplacementService:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        settings = load_settings()
        self.requested_provider = settings.preferredTtsProvider
        self.tts, self.provider_resolution_note = resolve_tts_provider(settings.preferredTtsProvider)
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
            settings={**request.controls.model_dump(), "provider": self.tts.name},
        )
        job = self.jobs.create(f"{self.kind}.replacement", project.id, client_job_id=request.clientJobId)
        job = self.jobs.update(job, status="running", progress=0.15, step="Inspecting segments", message="Analyzing source media")
        transcript_segments = self.segments.inspect(request.inputPath)
        combined_text = " ".join(segment.text for segment in transcript_segments)
        temp_audio = CACHE / f"{project.id}_replacement.wav"
        job = self.jobs.update(job, progress=0.45, step="Synthesizing replacement speech", message="Generating replacement voice track")
        self.tts.synthesize(combined_text, profile, request.controls, temp_audio)
        job = self.jobs.update(job, progress=0.75, step="Rendering output", message="Muxing final media output")
        output = self._render_media(request.inputPath, temp_audio, project.id)
        project = self.projects.finalize(project, str(output.resolve()))
        return self.jobs.update(job, status="completed", progress=1, step="Completed", message=f"{self.kind.title()} replacement complete", outputPath=project.outputPath)

    def _render_media(self, input_path: str, replacement_audio: Path, project_id: str) -> Path:
        ffmpeg = resolve_ffmpeg()
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
