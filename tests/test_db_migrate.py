import sqlite3

from core.config import settings
from core.db.migrate import run_migrations


def test_adds_missing_columns_and_is_idempotent(isolated_env):
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.execute(
        """
        CREATE TABLE chunks (
            id INTEGER PRIMARY KEY,
            session_id INTEGER,
            channel TEXT,
            speaker_label TEXT,
            audio_path TEXT,
            started_at TEXT,
            duration_ms INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE transcripts (
            id INTEGER PRIMARY KEY,
            chunk_id INTEGER,
            text TEXT,
            confidence REAL,
            language TEXT,
            needs_review INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY,
            started_at TEXT,
            ended_at TEXT,
            mode TEXT,
            status TEXT,
            vault_file TEXT,
            summary TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    run_migrations()
    run_migrations()

    conn = sqlite3.connect(settings.db_path)
    chunk_cols = {row[1] for row in conn.execute("PRAGMA table_info(chunks)")}
    session_cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
    transcript_cols = {row[1] for row in conn.execute("PRAGMA table_info(transcripts)")}
    conn.close()

    assert "source_app" in chunk_cols
    assert "is_echo" in chunk_cols
    assert "title" in session_cols
    assert "processing_state" in session_cols
    assert "processing_error" in transcript_cols
