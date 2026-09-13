from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException

from core.config import settings
from core.vault.writer import VaultWriter

router = APIRouter()


def _base() -> Path:
    if not settings.vault_path:
        raise HTTPException(404, "Vault yolu ayarlı değil")
    return settings.vault_path / "KatipAI"


@router.get("/vault/general")
def read_general_notes():
    path = VaultWriter().general_notes_path
    if not path.exists():
        return {"content": "", "path": str(path)}
    return {"content": path.read_text(encoding="utf-8"), "path": str(path)}


@router.get("/vault/daily/{day}")
def read_daily(day: str):
    base = _base()
    notes = base / "notes" / "daily" / f"{day}.md"
    transcript = base / "transcript" / f"{day}.md"
    return {
        "date": day,
        "notes": notes.read_text(encoding="utf-8") if notes.exists() else "",
        "transcript": transcript.read_text(encoding="utf-8") if transcript.exists() else "",
        "notes_path": str(notes),
        "transcript_path": str(transcript),
    }


@router.get("/vault/daily")
def read_today_vault():
    return read_daily(date.today().isoformat())
