from fastapi import APIRouter

from ..setup_status import get_setup_status

router = APIRouter(tags=["setup"])


@router.get("/setup-status")
def setup_status():
    return get_setup_status()
