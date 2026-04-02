from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..models import CreateVoiceProfileRequest, UpdateProfileReferenceRequest
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
    return service.create_profile_from_paths(request)


@router.post("/voice-profiles/upload")
async def create_profile_from_upload(
    name: str = Form(...),
    description: str = Form(""),
    authorizedUseConfirmed: bool = Form(False),
    clientJobId: str | None = Form(None),
    files: list[UploadFile] = File(...),
):
    if not authorizedUseConfirmed:
        raise HTTPException(status_code=400, detail="Authorized voice confirmation is required.")
    if not files:
        raise HTTPException(status_code=400, detail="At least one sample file is required.")
    payloads: list[tuple[str, bytes]] = []
    for file in files:
        payloads.append((file.filename or "sample.wav", await file.read()))
    return service.create_profile_from_uploads(
        name=name,
        description=description,
        authorized=authorizedUseConfirmed,
        files=payloads,
        client_job_id=clientJobId,
    )


@router.delete("/voice-profiles/{profile_id}")
def remove_profile(profile_id: str):
    delete_profile(profile_id)
    return {"ok": True}


@router.put("/voice-profiles/{profile_id}/reference")
def update_profile_reference(profile_id: str, request: UpdateProfileReferenceRequest):
    try:
        return service.update_reference(profile_id, request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
