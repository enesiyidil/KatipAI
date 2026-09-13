def test_status_idle_without_services(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["running"] is False
    assert body["state"] == "idle"
    assert body["mode"] == "normal"
