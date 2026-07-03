"""Persist and query selected system audio application sources."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from core.config import settings

logger = logging.getLogger(__name__)

SOURCES_FILE = settings.data_dir / "audio_sources.json"


def _helper_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "system_audio"
        / ".build"
        / "release"
        / "SystemAudioCapture"
    )


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
    """Return CLI args for SystemAudioCapture, or None if capture should not start."""
    helper = _helper_path()
    if not helper.exists():
        return None

    if settings.capture_all_system_audio:
        return [str(helper), "--capture", "--all"]

    bundle_ids = get_selected_apps()
    if not bundle_ids:
        return None

    return [str(helper), "--capture", "--apps", ",".join(bundle_ids)]


def source_app_label() -> str | None:
    if settings.capture_all_system_audio:
        return "all"
    apps = get_selected_apps()
    if not apps:
        return None
    return ",".join(apps)
