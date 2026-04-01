from fastapi import APIRouter

from ..models import SegmentInspectionRequest
from ..services import SegmentService

router = APIRouter(tags=["segments"])
service = SegmentService()


@router.post("/segments/audio")
def inspect_audio(request: SegmentInspectionRequest):
    return service.inspect(request.inputPath)


@router.post("/segments/video")
def inspect_video(request: SegmentInspectionRequest):
    return service.inspect(request.inputPath)
