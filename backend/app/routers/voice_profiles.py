from fastapi import APIRouter, HTTPException

from ..models import CreateVoiceProfileRequest
from ..services import VoiceProfileService
from ..storage import delete_profile, list_profiles

router = APIRouter(tags=["voiceProfiles"])
service = VoiceProfileService()


@router.get("/voice-profiles")
def get_profiles():
    return list_profiles()


@router.post("/voice-profiles")
def create_profile(request: CreateVoiceProfileRequest):
    if not request.authorizedUseConfirmed:
        raise HTTPException(status_code=400, detail="Authorized voice confirmation is required.")
    if not request.samplePaths:
        raise HTTPException(status_code=400, detail="At least one sample path is required.")
    return service.create_profile(request)


@router.delete("/voice-profiles/{profile_id}")
def remove_profile(profile_id: str):
    delete_profile(profile_id)
    return {"ok": True}
