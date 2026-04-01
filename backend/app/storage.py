from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar
from uuid import uuid4

from pydantic import BaseModel

from .models import AppSettings, JobRecord, ProjectRecord, VoiceProfile

T = TypeVar("T", bound=BaseModel)

ROOT = Path("storage")
PROFILES = ROOT / "profiles"
SAMPLES = ROOT / "samples"
PROJECTS = ROOT / "projects"
OUTPUTS = ROOT / "outputs"
JOBS = ROOT / "jobs"
CACHE = ROOT / "cache"
SETTINGS = ROOT / "settings.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_storage() -> None:
    for path in [ROOT, PROFILES, SAMPLES, PROJECTS, OUTPUTS, JOBS, CACHE]:
        path.mkdir(parents=True, exist_ok=True)
    if not SETTINGS.exists():
        SETTINGS.write_text(AppSettings().model_dump_json(indent=2), encoding="utf-8")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def read_model(path: Path, model_type: type[T]) -> T:
    ensure_storage()
    return model_type.model_validate_json(path.read_text(encoding="utf-8"))


def write_model(path: Path, model: BaseModel) -> None:
    ensure_storage()
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")


def load_settings() -> AppSettings:
    return read_model(SETTINGS, AppSettings)


def save_settings(settings: AppSettings) -> AppSettings:
    write_model(SETTINGS, settings)
    return settings


def list_profiles() -> list[VoiceProfile]:
    ensure_storage()
    return sorted(
        [read_model(path, VoiceProfile) for path in PROFILES.glob("*.json")],
        key=lambda item: item.updatedAt,
        reverse=True,
    )


def list_projects() -> list[ProjectRecord]:
    ensure_storage()
    return sorted(
        [read_model(path, ProjectRecord) for path in PROJECTS.glob("*.json")],
        key=lambda item: item.updatedAt,
        reverse=True,
    )


def list_jobs() -> list[JobRecord]:
    ensure_storage()
    return sorted(
        [read_model(path, JobRecord) for path in JOBS.glob("*.json")],
        key=lambda item: item.updatedAt,
        reverse=True,
    )


def save_profile(profile: VoiceProfile) -> VoiceProfile:
    write_model(PROFILES / f"{profile.id}.json", profile)
    return profile


def delete_profile(profile_id: str) -> None:
    path = PROFILES / f"{profile_id}.json"
    if path.exists():
        path.unlink()


def read_profile(profile_id: str) -> VoiceProfile:
    return read_model(PROFILES / f"{profile_id}.json", VoiceProfile)


def save_project(project: ProjectRecord) -> ProjectRecord:
    write_model(PROJECTS / f"{project.id}.json", project)
    return project


def save_job(job: JobRecord) -> JobRecord:
    write_model(JOBS / f"{job.id}.json", job)
    return job


def copy_to_profile_sample_area(profile_id: str, source_path: str) -> str:
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Sample does not exist: {source}")
    target_dir = SAMPLES / profile_id
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / source.name
    destination.write_bytes(source.read_bytes())
    return str(destination.resolve())
