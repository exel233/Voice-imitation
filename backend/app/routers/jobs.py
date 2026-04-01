from fastapi import APIRouter

from ..storage import list_jobs

router = APIRouter(tags=["jobs"])


@router.get("/jobs")
def get_jobs():
    return list_jobs()
