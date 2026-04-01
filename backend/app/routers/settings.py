from fastapi import APIRouter

from ..models import AppSettings
from ..storage import load_settings, save_settings

router = APIRouter(tags=["settings"])


@router.get("/settings")
def get_settings():
    return load_settings()


@router.put("/settings")
def update_settings(partial: dict):
    current = load_settings()
    updated = current.model_copy(update=partial)
    validated = AppSettings.model_validate(updated.model_dump())
    return save_settings(validated)
