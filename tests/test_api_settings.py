def test_echo_threshold_bounds(client):
    too_low = client.patch("/api/settings", json={"echo_correlation_threshold": 0.1})
    assert too_low.status_code == 422
    too_high = client.patch("/api/settings", json={"echo_correlation_threshold": 1.5})
    assert too_high.status_code == 422


def test_persist_writes_isolated_env(client, isolated_env):
    env_file = isolated_env["env_file"]
    response = client.patch("/api/settings", json={"echo_correlation_threshold": 0.72})
    assert response.status_code == 200
    assert response.json()["echo_correlation_threshold"] == 0.72
    assert env_file.exists()
    text = env_file.read_text(encoding="utf-8")
    assert "KATIPAI_ECHO_CORRELATION_THRESHOLD=0.72" in text
    from pathlib import Path

    from core.api.routes.settings import get_env_file

    assert get_env_file() == Path(env_file)

