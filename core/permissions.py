"""Platform-aware permission checks and system settings deep links."""

from __future__ import annotations

import logging
import platform
import subprocess
import sys
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
MIC_SIGNAL_THRESHOLD = 0.002


def _helper_path() -> Path:
    from core.audio.app_sources import _helper_path as app_helper

    return app_helper()


def _helper_app_bundle() -> Path:
    from core.audio.app_sources import helper_app_bundle

    return helper_app_bundle()


def _probe_system_capture(seconds: float = 2.0) -> dict:
    from core.audio.capture import probe_system_capture

    return probe_system_capture(timeout=max(seconds, 8.0))


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
        from core.audio.app_sources import get_selected_apps
        from core.config import settings

        helper = _helper_path()
        app = _helper_app_bundle()
        if not app.exists():
            return {
                "state": PermissionState.UNAVAILABLE.value,
                "message": "KatipAIAudioHelper.app bulunamadı",
                "hint": "bash tools/system_audio/build_helper.sh",
            }
        if not settings.system_enabled:
            return {"state": PermissionState.UNAVAILABLE.value, "message": "Sistem sesi ayarlarda kapalı"}
        if not settings.capture_all_system_audio and not get_selected_apps():
            return {
                "state": PermissionState.UNKNOWN.value,
                "message": "Uygulama seçilmedi — Ses Kaynakları bölümünden yapılandırın",
            }

        probe = _probe_system_capture(seconds=8.0)
        if probe["ok"]:
            return {
                "state": PermissionState.GRANTED.value,
                "message": "Sistem sesi yakalama çalışıyor",
                "hint": str(_helper_app_bundle()),
            }

        code = probe.get("code")
        if code == "permission_denied":
            app = _helper_app_bundle()
            return {
                "state": PermissionState.DENIED.value,
                "message": probe["message"],
                "hint": (
                    "Sistem Ayarları → Ekran ve Sistem Sesi Kaydı → "
                    "KatipAIAudioHelper (veya KatipAI Audio) açık olmalı"
                ),
                "helper_path": str(app if app.exists() else _helper_path()),
                "helper_name": "KatipAI Audio",
            }
        if code in ("no_matching_apps", "no_sources", "no_audio"):
            return {
                "state": PermissionState.UNKNOWN.value,
                "message": probe["message"],
                "hint": "Ses çıkaran uygulamayı açık tutun, Ses Kaynakları'ndan yeniden seçin",
            }

        return {
            "state": PermissionState.DENIED.value,
            "message": probe["message"],
            "hint": probe.get("stderr") or str(helper),
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


def request_system_audio_permission() -> dict:
    """Start capture briefly to trigger macOS Screen Recording prompt for KatipAI Audio."""
    app = _helper_app_bundle()
    if app.exists():
        subprocess.run(["open", "-a", str(app), "--args", "--list-apps"], check=False)
    probe = _probe_system_capture(seconds=3.0)
    check = check_system_audio()
    return {
        "ok": probe["ok"],
        "probe": probe,
        **check,
    }


def reveal_system_audio_helper() -> dict:
    app = _helper_app_bundle()
    if not app.exists():
        helper = _helper_path()
        if not helper.exists():
            return {
                "ok": False,
                "message": "Helper bulunamadı — tools/system_audio/build_helper.sh çalıştırın",
            }
        try:
            subprocess.run(["open", "-R", str(helper)], check=False)
            return {"ok": True, "message": f"Finder'da gösterildi: {helper}", "path": str(helper)}
        except Exception as e:
            return {"ok": False, "message": str(e)}
    try:
        subprocess.run(["open", "-R", str(app)], check=False)
        return {
            "ok": True,
            "message": (
                "Finder'da KatipAIAudioHelper.app gösterildi — "
                "Sistem Ayarları → Ekran ve Sistem Sesi Kaydı listesinde açık olmalı"
            ),
            "path": str(app),
        }
    except Exception as e:
        return {"ok": False, "message": str(e)}


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
    accessibility = {"state": PermissionState.UNAVAILABLE.value, "message": "Bu platformda desteklenmiyor"}
    if plat == "macos":
        from core.audio.teams_title import check_accessibility_for_teams

        accessibility = check_accessibility_for_teams()
    return {
        "platform": plat,
        "platform_label": {"macos": "macOS", "windows": "Windows", "linux": "Linux"}.get(plat, plat),
        "os_version": platform.platform(),
        "microphone": check_microphone(),
        "system_audio": check_system_audio(),
        "accessibility": accessibility,
        "settings_urls": {k: v["label"] for k, v in get_settings_urls().items()},
        "steps": _setup_steps(plat),
    }


def _setup_steps(plat: str) -> list[dict]:
    if plat == "macos":
        return [
            {"id": "mic_request", "title": "Mikrofon izni iste", "action": "request_microphone"},
            {"id": "mic_settings", "title": "Mikrofon ayarlarını aç", "action": "open_microphone"},
            {"id": "screen_settings", "title": "Ekran kaydı ayarlarını aç", "action": "open_screen_recording"},
            {"id": "accessibility_settings", "title": "Erişilebilirlik ayarlarını aç", "action": "open_accessibility"},
            {"id": "system_request", "title": "Sistem sesi izni iste", "action": "request_system_audio"},
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
