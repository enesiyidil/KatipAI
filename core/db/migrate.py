"""Idempotent SQLite migrations for existing KatipAI databases."""

import logging
import sqlite3

from core.config import settings

logger = logging.getLogger(__name__)

CHUNK_COLUMNS = [
    ("source_app", "TEXT"),
    ("is_echo", "INTEGER DEFAULT 0"),
    ("echo_score", "REAL"),
    ("voice_match_score", "REAL"),
    ("skip_reason", "TEXT"),
    ("speaker_id", "INTEGER"),
]

TRANSCRIPT_COLUMNS = [
    ("processing_error", "TEXT"),
]

SESSION_COLUMNS = [
    ("title", "TEXT"),
    ("title_source", "VARCHAR(32)"),
    ("participants_hint", "TEXT"),
    ("duration_ms", "INTEGER"),
    ("processing_state", "VARCHAR(32)"),
    ("processing_error", "TEXT"),
]


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _backfill_meeting_processing_state(conn: sqlite3.Connection) -> None:
    """Set processing_state for existing meeting sessions."""
    if "processing_state" not in _existing_columns(conn, "sessions"):
        return
    conn.execute(
        """
        UPDATE sessions SET processing_state = 'ready'
        WHERE mode = 'meeting' AND processing_state IS NULL AND summary IS NOT NULL AND summary != ''
        """
    )
    conn.execute(
        """
        UPDATE sessions SET processing_state = 'failed'
        WHERE mode = 'meeting' AND processing_state IS NULL
          AND id IN (
            SELECT DISTINCT c.session_id FROM chunks c
            LEFT JOIN transcripts t ON t.chunk_id = c.id
            WHERE c.channel != 'meeting' AND t.id IS NULL
          )
        """
    )
    conn.execute(
        """
        UPDATE sessions SET processing_state = 'processing'
        WHERE mode = 'meeting' AND processing_state IS NULL
          AND ended_at IS NOT NULL
        """
    )
    conn.execute(
        """
        UPDATE sessions SET processing_state = 'recording'
        WHERE mode = 'meeting' AND processing_state IS NULL AND ended_at IS NULL
        """
    )


def run_migrations() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    if not settings.db_path.exists():
        return

    conn = sqlite3.connect(settings.db_path)
    try:
        cols = _existing_columns(conn, "chunks")
        for name, col_type in CHUNK_COLUMNS:
            if name not in cols:
                conn.execute(f"ALTER TABLE chunks ADD COLUMN {name} {col_type}")
                logger.info("Migration: added chunks.%s", name)

        transcript_cols = _existing_columns(conn, "transcripts")
        for name, col_type in TRANSCRIPT_COLUMNS:
            if name not in transcript_cols:
                conn.execute(f"ALTER TABLE transcripts ADD COLUMN {name} {col_type}")
                logger.info("Migration: added transcripts.%s", name)

        session_cols = _existing_columns(conn, "sessions")
        for name, col_type in SESSION_COLUMNS:
            if name not in session_cols:
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {name} {col_type}")
                logger.info("Migration: added sessions.%s", name)

        _backfill_meeting_processing_state(conn)

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS voice_profiles (
                id INTEGER PRIMARY KEY,
                embedding BLOB NOT NULL,
                sample_count INTEGER DEFAULT 1,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
