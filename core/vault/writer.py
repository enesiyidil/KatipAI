from datetime import datetime
from pathlib import Path

from core.config import settings


class VaultWriter:
    def __init__(self, vault_path: Path | None = None):
        self.vault_path = vault_path or settings.vault_path
        if self.vault_path:
            self.base = self.vault_path / "KatipAI"
            self.daily_dir = self.base / "daily"
            self.sessions_dir = self.base / "sessions"
            self.archive_dir = self.base / "archive" / "transcripts"
            for d in (self.daily_dir, self.sessions_dir, self.archive_dir):
                d.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return self.vault_path is not None

    def _daily_path(self, dt: datetime) -> Path:
        return self.daily_dir / f"{dt.strftime('%Y-%m-%d')}.md"

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
        if not self.enabled:
            return None

        stamp = started_at.strftime("%Y-%m-%d_%H-%M-%S")
        session_name = stamp
        session_path = self.sessions_dir / f"{session_name}.md"
        archive_path = self.archive_dir / f"{session_name}_full.md"

        speaker_yaml = ", ".join(speakers)
        tag_yaml = ", ".join(tags or ["katipai"])
        frontmatter = f"""---
type: katipai-session
date: {started_at.strftime('%Y-%m-%d')}
started: {started_at.strftime('%H:%M:%S')}
duration_min: {duration_min}
speakers: [{speaker_yaml}]
tags: [{tag_yaml}]
session_id: {session_id}
---

"""

        transcript_block = "\n".join(f"> {line}" for line in transcript_lines)
        session_content = f"""{frontmatter}# Oturum {started_at.strftime('%H:%M')}

{summary_md}

## Tam Transcript
Detay için: [[{session_name}_full|tam transcript]]

---
{transcript_block[:2000]}{"..." if len(transcript_block) > 2000 else ""}
"""
        session_path.write_text(session_content, encoding="utf-8")

        archive_content = f"""{frontmatter}# Tam Transcript — {started_at.strftime('%Y-%m-%d %H:%M')}

{chr(10).join(transcript_lines)}
"""
        archive_path.write_text(archive_content, encoding="utf-8")

        self._update_daily_index(started_at, session_name, duration_min, len(speakers))
        return session_path

    def _update_daily_index(self, dt: datetime, session_name: str, duration_min: int, speaker_count: int) -> None:
        daily_path = self._daily_path(dt)
        link_line = f"- [[{session_name}]] — {dt.strftime('%H:%M')}, {duration_min} dk, {speaker_count} konuşmacı"

        if daily_path.exists():
            content = daily_path.read_text(encoding="utf-8")
            if session_name in content:
                return
            if "## Oturumlar" in content:
                content = content.replace("## Oturumlar\n", f"## Oturumlar\n{link_line}\n", 1)
            else:
                content += f"\n## Oturumlar\n{link_line}\n"
        else:
            content = f"""# {dt.strftime('%Y-%m-%d')}

## Oturumlar
{link_line}

## Günün Özeti
_Oturumlar işlendikçe güncellenir._
"""
        daily_path.write_text(content, encoding="utf-8")
