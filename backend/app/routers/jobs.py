from fastapi import APIRouter, HTTPException

from ..storage import list_jobs, read_job

router = APIRouter(tags=["jobs"])


@router.get("/jobs")
def get_jobs():
    return list_jobs()


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    try:
        return read_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}") from exc
