from fastapi import APIRouter

from ..models import ReplacementRequest
from ..services import ReplacementService

router = APIRouter(tags=["videoReplacement"])
service = ReplacementService("video")


@router.post("/video-replacement")
def replace_video(request: ReplacementRequest):
    return service.process(request)
