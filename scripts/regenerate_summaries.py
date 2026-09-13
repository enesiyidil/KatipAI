#!/usr/bin/env python3
"""Regenerate session summaries into new daily notes structure."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.db.database import get_session, init_db
from core.db.models import Chunk, Session
from core.llm.summarizer import Summarizer
from core.vault.writer import VaultWriter


def regenerate(session_ids: list[int] | None = None):
    init_db()
    summarizer = Summarizer()
    vault = VaultWriter()

    with get_session() as db:
        q = db.query(Session).order_by(Session.started_at)
        if session_ids:
            q = q.filter(Session.id.in_(session_ids))
        target_ids = [s.id for s in q.all()]

    for sid in target_ids:
        with get_session() as db:
            session = db.get(Session, sid)
            if not session:
                continue
            chunks = (
                db.query(Chunk)
                .filter(Chunk.session_id == sid)
                .order_by(Chunk.started_at)
                .all()
            )
            lines = []
            started = session.started_at
            ended = session.ended_at
            for chunk in chunks:
                if chunk.transcript:
                    ts = chunk.started_at.strftime("%H:%M")
                    lines.append(f"[{ts}] **{chunk.speaker_label}**: {chunk.transcript.text}")
                    vault.append_transcript_line(
                        dt=chunk.started_at,
                        time_str=ts,
                        speaker=chunk.speaker_label,
                        text=chunk.transcript.text,
                    )

        if not lines:
            print(f"Session #{sid}: chunk yok, atlandı")
            continue

        print(f"Session #{sid}: özet üretiliyor...")
        summary = summarizer.summarize_session(lines)
        summarizer.unload()

        vault_path = vault.append_daily_ai_note(
            dt=started,
            time_str=started.strftime("%H:%M"),
            summary_md=summary,
            session_id=sid,
        )

        with get_session() as db:
            s = db.get(Session, sid)
            if s:
                s.summary = summary
                if vault_path:
                    s.vault_file = str(vault_path)

        print(f"  → {summary[:100]}...")


if __name__ == "__main__":
    ids = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else None
    regenerate(ids)
