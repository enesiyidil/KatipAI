from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import joinedload

from core.config import settings
from core.db.database import get_session
from core.db.models import Chunk, Transcript

router = APIRouter()


class ChunkUpdate(BaseModel):
    speaker_label: str | None = None


class TranscriptCorrection(BaseModel):
    corrected_text: str
    approved: bool = True


def _chunk_review_item(chunk: Chunk, transcript: Transcript | None, *, kind: str) -> dict:
    return {
        "kind": kind,
        "transcript_id": transcript.id if transcript else None,
        "chunk_id": chunk.id,
        "session_id": chunk.session_id,
        "text": (transcript.text if transcript else "") or "",
        "confidence": transcript.confidence if transcript else None,
        "processing_error": transcript.processing_error if transcript else None,
        "speaker": chunk.speaker_label,
        "channel": chunk.channel,
        "started_at": chunk.started_at.isoformat() if chunk.started_at else None,
        "time": chunk.started_at.strftime("%H:%M") if chunk.started_at else None,
        "duration_ms": chunk.duration_ms,
        "has_audio": bool(chunk.audio_path),
        "mode": chunk.session.mode if chunk.session else None,
    }


@router.get("/chunks/review-queue")
def review_queue():
    with get_session() as db:
        needs_review = (
            db.query(Transcript)
            .join(Chunk)
            .options(joinedload(Transcript.chunk).joinedload(Chunk.session))
            .filter(Transcript.needs_review.is_(True))
            .order_by(Transcript.id.desc())
            .limit(80)
            .all()
        )
        failed = (
            db.query(Transcript)
            .join(Chunk)
            .options(joinedload(Transcript.chunk).joinedload(Chunk.session))
            .filter(
                Transcript.processing_error.isnot(None),
                Transcript.needs_review.is_(False),
            )
            .order_by(Transcript.id.desc())
            .limit(40)
            .all()
        )
        items = []
        seen = set()
        for t in needs_review:
            if t.chunk_id in seen:
                continue
            seen.add(t.chunk_id)
            items.append(_chunk_review_item(t.chunk, t, kind="review"))
        for t in failed:
            if t.chunk_id in seen:
                continue
            seen.add(t.chunk_id)
            items.append(_chunk_review_item(t.chunk, t, kind="failed"))
        return items


@router.get("/chunks/{chunk_id}/audio")
def get_chunk_audio(chunk_id: int):
    with get_session() as db:
        chunk = db.get(Chunk, chunk_id)
        if not chunk or not chunk.audio_path:
            raise HTTPException(404, "Audio not found")
        path = Path(chunk.audio_path).resolve()
        audio_root = settings.audio_dir.resolve()
        try:
            path.relative_to(audio_root)
        except ValueError:
            raise HTTPException(403, "Invalid audio path")
        if not path.exists() or not path.is_file():
            raise HTTPException(404, "Audio file missing")
        media = "audio/wav" if path.suffix.lower() == ".wav" else "application/octet-stream"
        return FileResponse(path, media_type=media, filename=path.name)


@router.post("/chunks/reprocess-failed")
def reprocess_failed_chunks():
    from core.api.app import notify_clients, schedule_reprocess_chunk

    with get_session() as db:
        rows = (
            db.query(Chunk)
            .join(Transcript)
            .filter(Transcript.processing_error.isnot(None))
            .order_by(Chunk.id)
            .all()
        )
        chunk_ids = [c.id for c in rows]
        for chunk in rows:
            db.delete(chunk.transcript)

    scheduled = 0
    for chunk_id in chunk_ids:
        if schedule_reprocess_chunk(chunk_id):
            scheduled += 1
            notify_clients("chunk", chunk_id=chunk_id)

    return {"ok": True, "count": scheduled, "chunk_ids": chunk_ids}


@router.post("/chunks/{chunk_id}/reprocess")
def reprocess_chunk(chunk_id: int):
    from core.api.app import notify_clients, schedule_reprocess_chunk

    with get_session() as db:
        chunk = db.get(Chunk, chunk_id)
        if not chunk:
            raise HTTPException(404, "Chunk not found")
        if chunk.transcript:
            db.delete(chunk.transcript)
    scheduled = schedule_reprocess_chunk(chunk_id)
    if scheduled:
        notify_clients("chunk", chunk_id=chunk_id)
    return {"ok": scheduled, "chunk_id": chunk_id}


@router.patch("/chunks/{chunk_id}")
def update_chunk(chunk_id: int, body: ChunkUpdate):
    with get_session() as db:
        chunk = db.get(Chunk, chunk_id)
        if not chunk:
            return {"error": "not found"}
        if body.speaker_label:
            chunk.speaker_label = body.speaker_label
    return {"ok": True}


@router.post("/chunks/{chunk_id}/approve")
def approve_transcript(chunk_id: int):
    with get_session() as db:
        chunk = db.get(Chunk, chunk_id)
        if chunk and chunk.transcript:
            chunk.transcript.needs_review = False
    return {"ok": True}


@router.post("/transcripts/{transcript_id}/correct")
def correct_transcript(transcript_id: int, body: TranscriptCorrection):
    from core.db.models import Correction

    with get_session() as db:
        transcript = db.get(Transcript, transcript_id)
        if not transcript:
            return {"error": "not found"}
        correction = Correction(
            transcript_id=transcript_id,
            original=transcript.text,
            corrected=body.corrected_text,
            approved=body.approved,
        )
        transcript.text = body.corrected_text
        transcript.needs_review = False
        db.add(correction)
    return {"ok": True}
