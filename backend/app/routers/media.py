from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ..storage import is_storage_path

router = APIRouter(tags=["media"])


@router.get("/media")
def get_media(path: str = Query(...)):
    candidate = Path(path)
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="Media file not found.")
    if not is_storage_path(candidate):
        raise HTTPException(status_code=403, detail="Media access is restricted to local storage artifacts.")
    return FileResponse(candidate)
