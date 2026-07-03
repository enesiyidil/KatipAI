"""Platform-aware permission checks and system settings deep links."""

from __future__ import annotations

import logging
import platform
import subprocess
import sys
from enum import Enum

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
MIC_SIGNAL_THRESHOLD = 0.002


class PermissionState(str, Enum):
    GRANTED = "granted"
    DENIED = "denied"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


def get_platform() -> str:
    s = sys.platform
    if s == "darwin":
        return "macos"
    if s.startswith("win"):
        return "windows"
    return "linux"


def _probe_microphone(seconds: float = 1.5) -> tuple[float, float, str | None]:
    """Record briefly; return (rms, peak, error)."""
    try:
        import numpy as np
        import sounddevice as sd

        frames = int(SAMPLE_RATE * seconds)
        audio = sd.rec(frames, samplerate=SAMPLE_RATE, channels=1, dtype="float32")
        sd.wait()
        audio = audio.flatten()
        rms = float(np.sqrt(np.mean(audio**2)))
        peak = float(np.max(np.abs(audio)))
        return rms, peak, None
    except Exception as e:
        logger.warning("Mic probe failed: %s", e)
        return 0.0, 0.0, str(e)


def check_microphone() -> dict:
    rms, peak, err = _probe_microphone()
    if err:
        return {
            "state": PermissionState.DENIED.value,
            "rms": rms,
            "peak": peak,
            "message": f"Mikrofon erişilemedi: {err}",
        }
    if peak < 0.0001 and rms < 0.0001:
        return {
            "state": PermissionState.DENIED.value,
            "rms": rms,
            "peak": peak,
            "message": "Sinyal yok — izin kapalı veya yanlış cihaz",
        }
    if rms < MIC_SIGNAL_THRESHOLD:
        return {
            "state": PermissionState.UNKNOWN.value,
            "rms": rms,
            "peak": peak,
            "message": "Mikrofon açık ama ses zayıf — konuşarak tekrar test edin",
        }
    return {
        "state": PermissionState.GRANTED.value,
        "rms": rms,
        "peak": peak,
        "message": "Mikrofon çalışıyor",
    }


def check_system_audio() -> dict:
    plat = get_platform()
    if plat == "macos":
        from pathlib import Path

        from core.audio.app_sources import get_capture_args, get_selected_apps
        from core.config import settings

        helper = (
            Path(__file__).resolve().parents[1]
            / "tools"
            / "system_audio"
            / ".build"
            / "release"
            / "SystemAudioCapture"
        )
        if not helper.exists():
            return {
                "state": PermissionState.UNAVAILABLE.value,
                "message": "SystemAudioCapture derlenmemiş",
                "hint": "cd tools/system_audio && swift build -c release",
            }
        if not settings.system_enabled:
            return {"state": PermissionState.UNAVAILABLE.value, "message": "Sistem sesi ayarlarda kapalı"}
        if not settings.capture_all_system_audio and not get_selected_apps():
            return {
                "state": PermissionState.UNKNOWN.value,
                "message": "Uygulama seçilmedi — Ses Kaynakları bölümünden yapılandırın",
            }
        if get_capture_args() is None:
            return {"state": PermissionState.DENIED.value, "message": "Sistem sesi capture başlatılamadı"}
        return {
            "state": PermissionState.UNKNOWN.value,
            "message": "Yapılandırıldı — Ekran Kaydı izni gerekebilir (macOS)",
            "hint": "Sistem Ayarları → Ekran Kaydı → Python",
        }
    if plat == "windows":
        return {
            "state": PermissionState.UNAVAILABLE.value,
            "message": "Sistem sesi capture şu an yalnızca macOS'ta destekleniyor",
            "hint": "Mikrofon iznini Windows ayarlarından verin",
        }
    return {"state": PermissionState.UNAVAILABLE.value, "message": "Bu platformda sistem sesi henüz desteklenmiyor"}


def get_settings_urls() -> dict[str, dict]:
    plat = get_platform()
    if plat == "macos":
        base = "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension"
        return {
            "microphone": {
                "label": "Mikrofon Ayarları",
                "url": f"{base}?Privacy_Microphone",
                "fallback": "open /System/Library/PreferencePanes/Security.prefPane",
            },
            "screen_recording": {
                "label": "Ekran Kaydı Ayarları",
                "url": f"{base}?Privacy_ScreenCapture",
                "fallback": "open /System/Library/PreferencePanes/Security.prefPane",
            },
            "accessibility": {
                "label": "Erişilebilirlik Ayarları",
                "url": f"{base}?Privacy_Accessibility",
                "fallback": None,
            },
        }
    if plat == "windows":
        return {
            "microphone": {
                "label": "Mikrofon Gizliliği",
                "url": "ms-settings:privacy-microphone",
                "fallback": None,
            },
            "camera": {
                "label": "Uygulama İzinleri",
                "url": "ms-settings:privacy",
                "fallback": None,
            },
        }
    return {
        "microphone": {
            "label": "Ses Ayarları",
            "url": None,
            "fallback": "Sistem ses/mikrofon ayarlarını manuel açın",
        },
    }


def open_system_settings(permission: str) -> dict:
    urls = get_settings_urls()
    if permission not in urls:
        return {"ok": False, "message": f"Bilinmeyen izin: {permission}"}

    entry = urls[permission]
    plat = get_platform()
    url = entry.get("url")
    fallback = entry.get("fallback")

    try:
        if plat == "macos" and url:
            subprocess.run(["open", url], check=False)
            return {"ok": True, "message": f"{entry['label']} açıldı"}
        if plat == "windows" and url:
            subprocess.run(["cmd", "/c", "start", "", url], check=False)
            return {"ok": True, "message": f"{entry['label']} açıldı"}
        if fallback and fallback.startswith("open "):
            subprocess.run(fallback.split(), check=False)
            return {"ok": True, "message": "Sistem ayarları açıldı"}
        if fallback:
            return {"ok": False, "message": fallback}
        return {"ok": False, "message": "Bu platformda otomatik açılamıyor"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def request_microphone_permission() -> dict:
    """Short recording to trigger OS permission prompt."""
    rms, peak, err = _probe_microphone(seconds=2.0)
    check = check_microphone()
    return {
        "ok": check["state"] in (PermissionState.GRANTED.value, PermissionState.UNKNOWN.value),
        "probe": {"rms": rms, "peak": peak, "error": err},
        **check,
    }


def setup_all_permissions() -> dict:
    """Open all relevant settings + probe mic."""
    plat = get_platform()
    opened = []
    urls = get_settings_urls()

    mic_result = request_microphone_permission()

    for key in urls:
        if plat == "windows" and key == "camera":
            continue
        if plat == "macos" and key == "accessibility":
            continue
        res = open_system_settings(key)
        if res.get("ok"):
            opened.append(key)

    return {
        "platform": plat,
        "microphone": mic_result,
        "system_audio": check_system_audio(),
        "opened_settings": opened,
        "message": "İzin pencereleri açıldı — Python/Terminal için izin verin, ardından 'Kaydı yenile'ye basın",
    }


def full_status() -> dict:
    plat = get_platform()
    return {
        "platform": plat,
        "platform_label": {"macos": "macOS", "windows": "Windows", "linux": "Linux"}.get(plat, plat),
        "os_version": platform.platform(),
        "microphone": check_microphone(),
        "system_audio": check_system_audio(),
        "settings_urls": {k: v["label"] for k, v in get_settings_urls().items()},
        "steps": _setup_steps(plat),
    }


def _setup_steps(plat: str) -> list[dict]:
    if plat == "macos":
        return [
            {"id": "mic_request", "title": "Mikrofon izni iste", "action": "request_microphone"},
            {"id": "mic_settings", "title": "Mikrofon ayarlarını aç", "action": "open_microphone"},
            {"id": "screen_settings", "title": "Ekran kaydı ayarlarını aç", "action": "open_screen_recording"},
            {"id": "restart", "title": "Kaydı yenile", "action": "restart_capture"},
        ]
    if plat == "windows":
        return [
            {"id": "mic_request", "title": "Mikrofon izni iste", "action": "request_microphone"},
            {"id": "mic_settings", "title": "Mikrofon gizlilik ayarlarını aç", "action": "open_microphone"},
            {"id": "restart", "title": "Kaydı yenile", "action": "restart_capture"},
        ]
    return [
        {"id": "mic_request", "title": "Mikrofon testi", "action": "request_microphone"},
        {"id": "restart", "title": "Kaydı yenile", "action": "restart_capture"},
    ]
