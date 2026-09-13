from __future__ import annotations

import pytest


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    vault = tmp_path / "vault"
    env_file = tmp_path / ".env"
    data.mkdir()
    monkeypatch.setenv("KATIPAI_DATA_DIR", str(data))
    monkeypatch.setenv("KATIPAI_VAULT_PATH", str(vault))
    monkeypatch.setenv("KATIPAI_ENV_FILE", str(env_file))

    from core.config import settings
    from core.db.database import reset_engine

    previous_dir = settings.data_dir
    previous_vault = settings.vault_path
    settings.data_dir = data
    settings.vault_path = vault
    reset_engine()
    yield {"data": data, "vault": vault, "env_file": env_file, "tmp": tmp_path}
    settings.data_dir = previous_dir
    settings.vault_path = previous_vault
    reset_engine()
    from core import services

    services.recording_service = None
    services.note_pipeline = None


@pytest.fixture
def client(isolated_env):
    from core.api.app import create_app
    from fastapi.testclient import TestClient

    app = create_app(start_services=False)
    with TestClient(app) as test_client:
        yield test_client
