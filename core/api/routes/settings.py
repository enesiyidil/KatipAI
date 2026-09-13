import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from core.config import settings

router = APIRouter()


def get_env_file() -> Path:
    """Project `.env`, or `KATIPAI_ENV_FILE` when tests need isolation."""
    override = os.environ.get("KATIPAI_ENV_FILE")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / ".env"


def _read_env() -> dict[str, str]:
    path = get_env_file()
    if not path.exists():
        return {}
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    return result


def _persist_env(updates: dict[str, str | None]) -> None:
    env = _read_env()
    for key, value in updates.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    lines = [f"{k}={v}" for k, v in sorted(env.items())]
    path = get_env_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _persist_vault_path(path: str | None) -> None:
    _persist_env({"KATIPAI_VAULT_PATH": path})


class SettingsUpdate(BaseModel):
    vault_path: str | None = None
    mic_enabled: bool | None = None
    system_enabled: bool | None = None
    stt_model: str | None = None
    llm_model: str | None = None
    vad_threshold: float | None = None
    min_audio_rms: float | None = None
    echo_suppression_enabled: bool | None = None
    echo_correlation_threshold: float | None = Field(default=None, ge=0.3, le=0.99)
    voice_filter_mode: str | None = None
    voice_match_threshold: float | None = Field(default=None, ge=0.5, le=0.99)
    capture_all_system_audio: bool | None = None


def _settings_dict() -> dict:
    return {
        "vault_path": str(settings.vault_path) if settings.vault_path else None,
        "mic_enabled": settings.mic_enabled,
        "system_enabled": settings.system_enabled,
        "stt_model": settings.stt_model,
        "stt_fallback_model": settings.stt_fallback_model,
        "llm_model": settings.llm_model,
        "llm_fallback_model": settings.llm_fallback_model,
        "vad_threshold": settings.vad_threshold,
        "min_audio_rms": settings.min_audio_rms,
        "echo_suppression_enabled": settings.echo_suppression_enabled,
        "echo_correlation_threshold": settings.echo_correlation_threshold,
        "voice_filter_mode": settings.voice_filter_mode,
        "voice_match_threshold": settings.voice_match_threshold,
        "capture_all_system_audio": settings.capture_all_system_audio,
        "api_enabled": False,
        "api_note": "API entegrasyonu yakında — şimdilik tamamen lokal",
    }


@router.get("/settings")
def get_settings():
    return _settings_dict()


@router.patch("/settings")
def update_settings(body: SettingsUpdate):
    env_updates: dict[str, str | None] = {}

    if body.vault_path is not None:
        settings.vault_path = Path(body.vault_path) if body.vault_path else None
        env_updates["KATIPAI_VAULT_PATH"] = body.vault_path
    if body.mic_enabled is not None:
        settings.mic_enabled = body.mic_enabled
        from core import services

        if services.recording_service and services.recording_service.is_running:
            services.recording_service.restart_all_capture()
    if body.system_enabled is not None:
        settings.system_enabled = body.system_enabled
        from core import services

        if services.recording_service and services.recording_service.is_running:
            services.recording_service.restart_all_capture()
    if body.stt_model is not None:
        settings.stt_model = body.stt_model
    if body.llm_model is not None:
        settings.llm_model = body.llm_model
    if body.vad_threshold is not None:
        settings.vad_threshold = body.vad_threshold
    if body.min_audio_rms is not None:
        settings.min_audio_rms = body.min_audio_rms
    if body.echo_suppression_enabled is not None:
        settings.echo_suppression_enabled = body.echo_suppression_enabled
        env_updates["KATIPAI_ECHO_SUPPRESSION_ENABLED"] = str(body.echo_suppression_enabled).lower()
    if body.echo_correlation_threshold is not None:
        settings.echo_correlation_threshold = body.echo_correlation_threshold
        env_updates["KATIPAI_ECHO_CORRELATION_THRESHOLD"] = str(body.echo_correlation_threshold)
    if body.voice_filter_mode is not None:
        if body.voice_filter_mode not in ("strict", "prefer", "off"):
            from fastapi import HTTPException

            raise HTTPException(400, "voice_filter_mode must be strict, prefer, or off")
        settings.voice_filter_mode = body.voice_filter_mode
        env_updates["KATIPAI_VOICE_FILTER_MODE"] = body.voice_filter_mode
    if body.voice_match_threshold is not None:
        settings.voice_match_threshold = body.voice_match_threshold
        env_updates["KATIPAI_VOICE_MATCH_THRESHOLD"] = str(body.voice_match_threshold)
    if body.capture_all_system_audio is not None:
        from core.audio.app_sources import apply_audio_source_settings

        apply_audio_source_settings(capture_all_system_audio=body.capture_all_system_audio)
        env_updates["KATIPAI_CAPTURE_ALL_SYSTEM_AUDIO"] = str(body.capture_all_system_audio).lower()

    if env_updates:
        _persist_env(env_updates)

    return _settings_dict()
