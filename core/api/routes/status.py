from fastapi import APIRouter, HTTPException

from core import services
from core.db.models import RecordingMode

router = APIRouter()


def _pipeline_info() -> dict[str, int | bool]:
    from core.api.app import get_pipeline_info

    return get_pipeline_info()


def _status_payload():
    svc = services.recording_service
    pipeline = _pipeline_info()
    state = svc.app_state.value if svc else "idle"
    if pipeline["busy"] and state == "listening":
        state = "processing"
    return {
        "state": state,
        "raw_state": svc.app_state.value if svc else "idle",
        "mode": svc.mode.value if svc else "normal",
        "session_id": svc.session_id if svc else None,
        "running": svc.is_running if svc else False,
        "pipeline": pipeline,
    }


@router.get("/status")
def get_status():
    return _status_payload()


@router.post("/start")
def start():
    svc = services.recording_service
    if not svc:
        raise HTTPException(503, "Recording service unavailable")
    ok = svc.start()
    return {"ok": ok, **_status_payload()}


@router.post("/stop")
def stop():
    svc = services.recording_service
    if not svc:
        raise HTTPException(503, "Recording service unavailable")
    ok = svc.stop()
    return {"ok": ok, **_status_payload()}


@router.post("/pause")
def pause():
    svc = services.recording_service
    if not svc:
        raise HTTPException(503, "Recording service unavailable")
    ok = svc.pause()
    return {"ok": ok, **_status_payload()}


@router.post("/resume")
def resume():
    svc = services.recording_service
    if not svc:
        raise HTTPException(503, "Recording service unavailable")
    ok = svc.resume()
    return {"ok": ok, **_status_payload()}


@router.post("/mode/{mode}")
def set_mode(mode: str):
    try:
        recording_mode = RecordingMode(mode)
    except ValueError:
        raise HTTPException(400, f"Invalid mode: {mode}")
    svc = services.recording_service
    if not svc:
        raise HTTPException(503, "Recording service unavailable")
    svc.set_mode(recording_mode)
    return {"ok": True, **_status_payload()}


@router.post("/manual-record")
def manual_record():
    svc = services.recording_service
    if not svc:
        raise HTTPException(503, "Recording service unavailable")
    if not svc.is_running:
        raise HTTPException(409, "Dinleme kapalı — önce başlatın")
    svc.manual_record_start()
    return {"ok": True, **_status_payload()}


@router.post("/delete-last-chunk")
def delete_last_chunk():
    chunk_id = None
    if services.recording_service:
        chunk_id = services.recording_service.delete_last_chunk()
    if chunk_id is not None:
        from core.api.app import notify_clients

        notify_clients("chunk_deleted", chunk_id=chunk_id)
    return {"ok": chunk_id is not None, "chunk_id": chunk_id}
