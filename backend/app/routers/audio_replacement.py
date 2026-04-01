from fastapi import APIRouter

from ..models import ReplacementRequest
from ..services import ReplacementService

router = APIRouter(tags=["audioReplacement"])
service = ReplacementService("audio")


@router.post("/audio-replacement")
def replace_audio(request: ReplacementRequest):
    return service.process(request)
