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


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


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
