"""Delete recorded audio files older than the configured retention window."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def purge_expired_audio(
    audio_dir: Path,
    days: int,
    *,
    now: datetime | None = None,
) -> int:
    """Remove files under ``audio_dir`` older than ``days``.

    ``days <= 0`` disables purging. ``now`` is injectable for tests.
    Returns the number of files deleted.
    """
    if days <= 0:
        return 0
    if not audio_dir.exists():
        return 0

    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    cutoff = clock.timestamp() - days * 86400
    removed = 0
    for path in audio_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        except OSError as exc:
            logger.warning("Could not purge %s: %s", path, exc)
    if removed:
        logger.info("Purged %d expired audio file(s) (retention=%d days)", removed, days)
    return removed
