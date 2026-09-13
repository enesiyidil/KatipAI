from fastapi import APIRouter
from pydantic import BaseModel

from core import services
from core.audio.app_sources import apply_audio_source_settings, capture_config_snapshot

router = APIRouter()


class AudioSourcesUpdate(BaseModel):
    bundle_ids: list[str]
    capture_all_system_audio: bool | None = None


@router.get("/audio/apps")
def get_audio_apps():
    from core.audio.app_sources import list_available_apps

    return {"apps": list_available_apps()}


@router.get("/audio/sources")
def get_audio_sources():
    if services.recording_service:
        return services.recording_service.get_system_capture_status()
    snap = capture_config_snapshot()
    return {
        **snap,
        "listening": False,
        "system_enabled": True,
        "system_capture_active": False,
        "last_error": None,
    }


@router.put("/audio/sources")
def update_audio_sources(body: AudioSourcesUpdate):
    result = apply_audio_source_settings(
        bundle_ids=body.bundle_ids,
        capture_all_system_audio=body.capture_all_system_audio,
    )
    if body.capture_all_system_audio is not None:
        _persist_capture_all(body.capture_all_system_audio)
    return result


@router.post("/audio/sources/refresh")
def refresh_audio_apps():
    from core.audio.app_sources import list_available_apps

    return {"apps": list_available_apps()}


def _persist_capture_all(value: bool) -> None:
    from core.api.routes.settings import _persist_env

    _persist_env({"KATIPAI_CAPTURE_ALL_SYSTEM_AUDIO": str(value).lower()})
