from fastapi import APIRouter
from pydantic import BaseModel

from core.db.database import get_session
from core.db.models import Chunk, Transcript

router = APIRouter()


class ChunkUpdate(BaseModel):
    speaker_label: str | None = None


class TranscriptCorrection(BaseModel):
    corrected_text: str
    approved: bool = True


@router.get("/chunks/review-queue")
def review_queue():
    with get_session() as db:
        rows = (
            db.query(Transcript)
            .filter(Transcript.needs_review.is_(True))
            .order_by(Transcript.id.desc())
            .limit(100)
            .all()
        )
        return [
            {
                "transcript_id": t.id,
                "chunk_id": t.chunk_id,
                "text": t.text,
                "confidence": t.confidence,
            }
            for t in rows
        ]


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
