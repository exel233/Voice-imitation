from fastapi import APIRouter

from ..storage import list_jobs, list_profiles, list_projects, load_settings

router = APIRouter(tags=["overview"])


@router.get("/overview")
def get_overview():
    return {
        "profiles": list_profiles(),
        "projects": list_projects(),
        "jobs": list_jobs(),
        "settings": load_settings(),
    }
