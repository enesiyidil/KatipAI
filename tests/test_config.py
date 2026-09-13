from core.config import Settings


def test_defaults_and_audio_dir():
    s = Settings(_env_file=None)
    assert s.host == "127.0.0.1"
    assert s.port == 8742
    assert s.audio_dir == s.data_dir / "audio"
    assert s.db_path == s.data_dir / "katipai.db"


def test_env_prefix(monkeypatch):
    monkeypatch.setenv("KATIPAI_PORT", "9001")
    monkeypatch.setenv("KATIPAI_HOST", "127.0.0.1")
    s = Settings(_env_file=None)
    assert s.port == 9001
