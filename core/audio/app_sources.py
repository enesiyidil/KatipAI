"""Persist and query selected system audio application sources."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from core.config import settings

logger = logging.getLogger(__name__)

SOURCES_FILE = settings.data_dir / "audio_sources.json"
HELPER_ROOT = Path(__file__).resolve().parents[2] / "tools" / "system_audio"
HELPER_APP = HELPER_ROOT / "KatipAIAudioHelper.app"
HELPER_BIN_RAW = HELPER_ROOT / ".build" / "release" / "SystemAudioCapture"


def helper_app_bundle() -> Path:
    return HELPER_APP


def _helper_path() -> Path:
    app_bin = HELPER_APP / "Contents" / "MacOS" / "KatipAIAudioHelper"
    if app_bin.exists():
        return app_bin
    return HELPER_BIN_RAW


def helper_binary_path() -> Path:
    return _helper_path()


def helper_display_name() -> str:
    return "KatipAI Audio"


def running_selected_bundle_ids() -> list[str]:
    """Selected bundle IDs that are currently running (required for ScreenCaptureKit)."""
    if settings.capture_all_system_audio:
        return []
    selected = get_selected_apps()
    if not selected:
        return []
    running = {app["bundle_id"] for app in list_available_apps()}
    return [bid for bid in selected if bid in running]


def list_available_apps() -> list[dict]:
    helper = _helper_path()
    if not helper.exists():
        logger.warning("System audio helper not built")
        return []
    try:
        result = subprocess.run(
            [str(helper), "--list-apps"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.warning("list-apps failed: %s", result.stderr)
            return []
        return json.loads(result.stdout.strip() or "[]")
    except Exception as e:
        logger.warning("Failed to list apps: %s", e)
        return []


def get_selected_apps() -> list[str]:
    if not SOURCES_FILE.exists():
        return []
    try:
        data = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
        return data.get("bundle_ids", [])
    except Exception:
        return []


def set_selected_apps(bundle_ids: list[str]) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    SOURCES_FILE.write_text(
        json.dumps({"bundle_ids": bundle_ids}, indent=2),
        encoding="utf-8",
    )


def get_capture_args() -> list[str] | None:
    """CLI args for direct helper invocation (list-apps, legacy)."""
    spec = get_capture_launch_spec()
    if spec is None:
        return None
    return [str(_helper_path()), *spec["args"]]


def get_capture_launch_spec() -> dict | None:
    """Launch spec for KatipAIAudioHelper.app via `open -a` (macOS TCC)."""
    if not HELPER_APP.exists() and not _helper_path().exists():
        return None

    args = ["--capture"]
    if settings.capture_all_system_audio:
        args.append("--all")
        bundle_ids: list[str] = []
    else:
        bundle_ids = running_selected_bundle_ids()
        if not bundle_ids:
            return None
        args.extend(["--apps", ",".join(bundle_ids)])

    return {"app": str(HELPER_APP), "args": args, "bundle_ids": bundle_ids}


KNOWN_APP_NAMES: dict[str, str] = {
    "com.microsoft.teams2": "Microsoft Teams",
    "com.microsoft.teams": "Microsoft Teams",
    "com.google.Chrome": "Chrome",
}


def friendly_app_name(bundle_id: str) -> str:
    if bundle_id in KNOWN_APP_NAMES:
        return KNOWN_APP_NAMES[bundle_id]
    if bundle_id.startswith("com.google.Chrome.app."):
        return "Chrome Uygulaması"
    parts = bundle_id.rsplit(".", 1)
    if len(parts) == 2 and parts[1][0].isupper():
        return parts[1].replace("_", " ")
    return bundle_id.split(".")[-1].replace("_", " ").title()


def active_capture_display_label() -> str | None:
    if settings.capture_all_system_audio:
        return "Tüm sistem sesi"
    running = running_selected_bundle_ids()
    if not running:
        return None
    return ", ".join(friendly_app_name(bid) for bid in running)


def system_speaker_label() -> str:
    """Speaker tag for system-channel chunks (e.g. Microsoft Teams)."""
    running = running_selected_bundle_ids()
    if not running:
        return "Diğer"
    if "com.microsoft.teams2" in running or "com.microsoft.teams" in running:
        return "Microsoft Teams"
    if len(running) == 1:
        return friendly_app_name(running[0])
    return ", ".join(friendly_app_name(bid) for bid in running[:2])


def source_app_label() -> str | None:
    return active_capture_display_label()


def capture_config_snapshot() -> dict:
    """Current source configuration and whether capture could start."""
    helper = _helper_path()
    bundle_ids = get_selected_apps()
    running_ids = running_selected_bundle_ids()
    capture_all = settings.capture_all_system_audio
    can_capture = helper.exists() and (capture_all or bool(running_ids))
    mode = "all" if capture_all else ("apps" if bundle_ids else "none")
    missing = [bid for bid in bundle_ids if bid not in set(running_ids)] if bundle_ids else []
    return {
        "bundle_ids": bundle_ids,
        "running_bundle_ids": running_ids,
        "missing_bundle_ids": missing,
        "capture_all_system_audio": capture_all,
        "helper_ready": helper.exists(),
        "helper_app": str(HELPER_APP) if HELPER_APP.exists() else None,
        "helper_name": helper_display_name(),
        "capture_mode": mode,
        "can_capture": can_capture,
    }


def apply_audio_source_settings(
    *,
    bundle_ids: list[str] | None = None,
    capture_all_system_audio: bool | None = None,
) -> dict:
    """Persist source selection and hot-restart system capture when listening."""
    from core import services

    if bundle_ids is not None:
        set_selected_apps(bundle_ids)
    if capture_all_system_audio is not None:
        settings.capture_all_system_audio = capture_all_system_audio

    snapshot = capture_config_snapshot()
    restart = None
    if services.recording_service:
        restart = services.recording_service.restart_system_capture()

    return {**snapshot, "restart": restart or {}}
