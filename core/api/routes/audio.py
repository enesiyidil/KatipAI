from fastapi import APIRouter
from pydantic import BaseModel

from core import services
from core.audio.app_sources import get_selected_apps, list_available_apps, set_selected_apps

router = APIRouter()


class AudioSourcesUpdate(BaseModel):
    bundle_ids: list[str]


@router.get("/audio/apps")
def get_audio_apps():
    return {"apps": list_available_apps()}


@router.get("/audio/sources")
def get_audio_sources():
    from core.config import settings

    return {
        "bundle_ids": get_selected_apps(),
        "capture_all_system_audio": settings.capture_all_system_audio,
    }


@router.put("/audio/sources")
def update_audio_sources(body: AudioSourcesUpdate):
    set_selected_apps(body.bundle_ids)
    if services.recording_service and services.recording_service.is_running:
        services.recording_service.restart_system_capture()
    return get_audio_sources()


@router.post("/audio/sources/refresh")
def refresh_audio_apps():
    return {"apps": list_available_apps()}
