from fastapi import APIRouter

from core.db.database import get_session
from core.db.models import Correction

router = APIRouter()


@router.get("/corrections")
def list_corrections(limit: int = 50):
    with get_session() as db:
        rows = db.query(Correction).order_by(Correction.created_at.desc()).limit(limit).all()
        return [
            {
                "id": c.id,
                "original": c.original,
                "corrected": c.corrected,
                "approved": c.approved,
            }
            for c in rows
        ]
