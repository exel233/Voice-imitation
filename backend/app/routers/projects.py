from fastapi import APIRouter

from ..storage import list_projects

router = APIRouter(tags=["projects"])


@router.get("/projects")
def get_projects():
    return list_projects()
