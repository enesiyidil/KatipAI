def test_jargon_crud(client):
    created = client.post("/api/jargon", json={"term": "deploy", "aliases": "yayın", "category": "dev"})
    assert created.status_code == 200
    jargon_id = created.json()["id"]

    listed = client.get("/api/jargon")
    assert listed.status_code == 200
    terms = [row["term"] for row in listed.json()]
    assert "deploy" in terms

    deleted = client.delete(f"/api/jargon/{jargon_id}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    after = client.get("/api/jargon")
    assert "deploy" not in [row["term"] for row in after.json()]
