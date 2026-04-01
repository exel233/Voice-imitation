from . import config  # noqa: F401
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (
    audio_replacement,
    jobs,
    media,
    overview,
    projects,
    segments,
    setup,
    settings,
    tts,
    video_replacement,
    voice_profiles,
)

app = FastAPI(title="Voice Imitation Studio Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(overview.router, prefix="/api")
app.include_router(media.router, prefix="/api")
app.include_router(voice_profiles.router, prefix="/api")
app.include_router(tts.router, prefix="/api")
app.include_router(audio_replacement.router, prefix="/api")
app.include_router(video_replacement.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(segments.router, prefix="/api")
app.include_router(setup.router, prefix="/api")
