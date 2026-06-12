from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from core.config import settings

router = APIRouter()

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


def _persist_vault_path(path: str | None) -> None:
    lines: list[str] = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    key = "KATIPAI_VAULT_PATH="
    filtered = [ln for ln in lines if not ln.startswith(key)]
    if path:
        filtered.append(f"{key}{path}")
    ENV_FILE.write_text("\n".join(filtered) + ("\n" if filtered else ""), encoding="utf-8")


class SettingsUpdate(BaseModel):
    vault_path: str | None = None
    mic_enabled: bool | None = None
    system_enabled: bool | None = None
    stt_model: str | None = None
    llm_model: str | None = None
    vad_threshold: float | None = None


@router.get("/settings")
def get_settings():
    return {
        "vault_path": str(settings.vault_path) if settings.vault_path else None,
        "mic_enabled": settings.mic_enabled,
        "system_enabled": settings.system_enabled,
        "stt_model": settings.stt_model,
        "stt_fallback_model": settings.stt_fallback_model,
        "llm_model": settings.llm_model,
        "llm_fallback_model": settings.llm_fallback_model,
        "vad_threshold": settings.vad_threshold,
        "api_enabled": False,
        "api_note": "API entegrasyonu yakında — şimdilik tamamen lokal",
    }


@router.patch("/settings")
def update_settings(body: SettingsUpdate):
    if body.vault_path is not None:
        settings.vault_path = Path(body.vault_path) if body.vault_path else None
        _persist_vault_path(body.vault_path)
    if body.mic_enabled is not None:
        settings.mic_enabled = body.mic_enabled
    if body.system_enabled is not None:
        settings.system_enabled = body.system_enabled
    if body.stt_model is not None:
        settings.stt_model = body.stt_model
    if body.llm_model is not None:
        settings.llm_model = body.llm_model
    if body.vad_threshold is not None:
        settings.vad_threshold = body.vad_threshold
    return get_settings()
