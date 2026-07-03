from datetime import datetime
from pathlib import Path

from core.config import settings


class VaultWriter:
    """
    Obsidian vault yapısı:

    KatipAI/
      transcript/2026-06-12.md     — günlük ham transcript (chunk chunk eklenir)
      notes/daily/2026-06-12.md    — günlük AI notları (oturum özetleri)
      general/Notlar.md            — kalıcı genel notlar (sesli komutla)
    """

    def __init__(self, vault_path: Path | None = None):
        self.vault_path = vault_path or settings.vault_path
        if self.vault_path:
            self.base = self.vault_path / "KatipAI"
            self.transcript_dir = self.base / "transcript"
            self.daily_notes_dir = self.base / "notes" / "daily"
            self.general_dir = self.base / "general"
            for d in (self.transcript_dir, self.daily_notes_dir, self.general_dir):
                d.mkdir(parents=True, exist_ok=True)
            self._ensure_index()

    @property
    def enabled(self) -> bool:
        return self.vault_path is not None

    def _ensure_index(self) -> None:
        index = self.base / "README.md"
        if index.exists():
            return
        index.write_text(
            """# KatipAI

- [[transcript/]] — Günlük ham transcript kayıtları
- [[notes/daily/]] — Günlük AI notları
- [[general/Notlar|Genel Notlar]] — Kalıcı genel notlar

> "Bunu genel notlara ekle" dediğinde notlar `general/Notlar.md` dosyasına yazılır.
""",
            encoding="utf-8",
        )

    def _transcript_path(self, dt: datetime) -> Path:
        return self.transcript_dir / f"{dt.strftime('%Y-%m-%d')}.md"

    def _daily_note_path(self, dt: datetime) -> Path:
        return self.daily_notes_dir / f"{dt.strftime('%Y-%m-%d')}.md"

    @property
    def general_notes_path(self) -> Path:
        return self.general_dir / "Notlar.md"

    def _init_transcript_day(self, path: Path, dt: datetime) -> None:
        path.write_text(
            f"""---
type: katipai-transcript-day
date: {dt.strftime('%Y-%m-%d')}
tags: [katipai, transcript]
---

# Transcript — {dt.strftime('%Y-%m-%d')}

""",
            encoding="utf-8",
        )

    def _init_daily_notes_day(self, path: Path, dt: datetime) -> None:
        path.write_text(
            f"""---
type: katipai-notes-day
date: {dt.strftime('%Y-%m-%d')}
tags: [katipai, notes]
---

# AI Notları — {dt.strftime('%Y-%m-%d')}

""",
            encoding="utf-8",
        )

    def append_transcript_line(
        self,
        dt: datetime,
        time_str: str,
        speaker: str,
        text: str,
    ) -> Path | None:
        if not self.enabled or not text.strip():
            return None

        path = self._transcript_path(dt)
        if not path.exists():
            self._init_transcript_day(path, dt)

        entry = f"\n### {time_str} — {speaker}\n\n{text.strip()}\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(entry)
        return path

    def append_daily_ai_note(
        self,
        dt: datetime,
        time_str: str,
        summary_md: str,
        session_id: int,
    ) -> Path | None:
        if not self.enabled or not summary_md.strip():
            return None

        path = self._daily_note_path(dt)
        if not path.exists():
            self._init_daily_notes_day(path, dt)

        block = f"\n## Oturum {time_str} `#{session_id}`\n\n{summary_md.strip()}\n\n---\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(block)
        return path

    def append_general_note(
        self,
        dt: datetime,
        time_str: str,
        note_text: str,
        source_transcript: str | None = None,
    ) -> Path | None:
        if not self.enabled or not note_text.strip():
            return None

        path = self.general_notes_path
        if not path.exists():
            path.write_text(
                """---
type: katipai-general-notes
tags: [katipai, genel-notlar]
---

# Genel Notlar

Kalıcı notlar — sesli komutla eklenir: *"bunu genel notlara ekle"*

---

""",
                encoding="utf-8",
            )

        block = f"""
## {dt.strftime('%Y-%m-%d')} {time_str}

{note_text.strip()}

"""
        if source_transcript and source_transcript.strip() != note_text.strip():
            block += f"> Kaynak: _{source_transcript.strip()}_\n\n"

        block += "---\n"

        with path.open("a", encoding="utf-8") as f:
            f.write(block)
        return path

    def write_session(
        self,
        session_id: int,
        started_at: datetime,
        duration_min: int,
        speakers: list[str],
        summary_md: str,
        transcript_lines: list[str],
        tags: list[str] | None = None,
    ) -> Path | None:
        """Oturum sonu: günlük AI not dosyasına özet ekle."""
        if not self.enabled:
            return None
        return self.append_daily_ai_note(
            dt=started_at,
            time_str=started_at.strftime("%H:%M"),
            summary_md=summary_md,
            session_id=session_id,
        )
