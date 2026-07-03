from fastapi import APIRouter

from core import permissions, services

router = APIRouter()


@router.get("/permissions/status")
def permissions_status():
    return permissions.full_status()


@router.post("/permissions/request/microphone")
def request_microphone():
    return permissions.request_microphone_permission()


@router.post("/permissions/open/{permission}")
def open_permission_settings(permission: str):
    return permissions.open_system_settings(permission)


@router.post("/permissions/setup")
def setup_permissions():
    return permissions.setup_all_permissions()


@router.post("/permissions/restart-capture")
def restart_capture():
    svc = services.recording_service
    if not svc:
        return {"ok": False, "message": "Recording service unavailable"}
    if svc.is_running:
        svc.restart_all_capture()
    else:
        svc.start()
    return {
        "ok": True,
        "message": "Kayıt yeniden başlatıldı",
        "state": svc.app_state.value,
    }
