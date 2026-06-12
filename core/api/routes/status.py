from fastapi import APIRouter

from core import services
from core.db.models import RecordingMode

router = APIRouter()


@router.get("/status")
def get_status():
    svc = services.recording_service
    return {
        "state": svc.app_state.value if svc else "idle",
        "mode": svc.mode.value if svc else "normal",
        "session_id": svc.session_id if svc else None,
    }


@router.post("/pause")
def pause():
    if services.recording_service:
        services.recording_service.pause()
    return {"ok": True}


@router.post("/resume")
def resume():
    if services.recording_service:
        services.recording_service.resume()
    return {"ok": True}


@router.post("/mode/{mode}")
def set_mode(mode: str):
    if services.recording_service:
        services.recording_service.set_mode(RecordingMode(mode))
    return {"ok": True, "mode": mode}


@router.post("/manual-record")
def manual_record():
    if services.recording_service:
        services.recording_service.manual_record_start()
    return {"ok": True}


@router.post("/delete-last-chunk")
def delete_last_chunk():
    ok = services.recording_service.delete_last_chunk() if services.recording_service else False
    return {"ok": ok}
