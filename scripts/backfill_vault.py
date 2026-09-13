#!/usr/bin/env python3
"""Bugünkü transcript vault + eksik özetleri + genel notları senkronize et."""

import asyncio
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.db.database import get_session, init_db
from core.db.models import Chunk, Session, Transcript
from core.pipeline.note_pipeline import NotePipeline
from core.vault.general_notes import extract_general_note, is_general_note_command
from core.vault.writer import VaultWriter


async def backfill():
    init_db()
    vault = VaultWriter()
    pipeline = NotePipeline()
    today = date.today()

    # Transcript dosyasını sıfırdan oluştur
    tpath = vault._transcript_path(datetime.combine(today, datetime.min.time()))
    vault._init_transcript_day(tpath, datetime.combine(today, datetime.min.time()))

    with get_session() as db:
        rows = (
            db.query(Chunk, Transcript)
            .outerjoin(Transcript, Transcript.chunk_id == Chunk.id)
            .join(Session)
            .filter(Session.started_at >= datetime.combine(today, datetime.min.time()))
            .order_by(Chunk.started_at)
            .all()
        )
        items = [
            {
                "started_at": chunk.started_at,
                "speaker": chunk.speaker_label,
                "text": transcript.text if transcript else "",
            }
            for chunk, transcript in rows
        ]

    print(f"Transcript backfill: {len(items)} chunk")
    for item in items:
        text = item["text"].strip()
        if not text:
            continue
        dt = item["started_at"]
        time_str = dt.strftime("%H:%M")
        vault.append_transcript_line(
            dt=dt,
            time_str=time_str,
            speaker=item["speaker"],
            text=text,
        )
        if is_general_note_command(text):
            note = extract_general_note(text)
            vault.append_general_note(
                dt=dt,
                time_str=time_str,
                note_text=note,
                source_transcript=text,
            )
            print(f"  Genel not: {note[:60]}")

    # Eksik özetler
    with get_session() as db:
        pending = (
            db.query(Session)
            .filter(Session.started_at >= datetime.combine(today, datetime.min.time()))
            .filter(Session.summary.is_(None))
            .all()
        )
        pending_ids = [s.id for s in pending]

    for sid in pending_ids:
        with get_session() as db:
            chunks = db.query(Chunk).filter(Chunk.session_id == sid).all()
            if not chunks or any(c.transcript is None for c in chunks):
                print(f"Session #{sid}: atlandı (chunk/transcript eksik)")
                continue
        print(f"Session #{sid}: özet üretiliyor...")
        await pipeline.finalize_session(sid)

    print("Backfill tamamlandı.")


if __name__ == "__main__":
    asyncio.run(backfill())
