from datetime import datetime, timedelta, timezone

from core.audio.retention import purge_expired_audio


def test_purges_old_files_keeps_new(tmp_path):
    audio = tmp_path / "audio"
    audio.mkdir()
    old = audio / "old.wav"
    new = audio / "new.wav"
    old.write_bytes(b"old")
    new.write_bytes(b"new")
    now = datetime.now(timezone.utc)
    stale = now - timedelta(days=10)
    old.touch()
    import os

    os.utime(old, (stale.timestamp(), stale.timestamp()))

    removed = purge_expired_audio(audio, 7, now=now)
    assert removed == 1
    assert not old.exists()
    assert new.exists()


def test_days_zero_or_missing_dir(tmp_path):
    missing = tmp_path / "nope"
    assert purge_expired_audio(missing, 7) == 0
    audio = tmp_path / "audio"
    audio.mkdir()
    keep = audio / "keep.wav"
    keep.write_bytes(b"x")
    assert purge_expired_audio(audio, 0) == 0
    assert keep.exists()
