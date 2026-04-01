from fastapi import APIRouter

from ..models import TtsRequest
from ..services import TtsService

router = APIRouter(tags=["tts"])
service = TtsService()


@router.post("/tts/synthesize")
def synthesize(request: TtsRequest):
    return service.synthesize(request)
