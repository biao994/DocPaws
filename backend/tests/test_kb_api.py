def test_create_kb_then_list(auth_client):
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": "d"},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    r2 = auth_client.get("/api/v1/knowledge-bases?page=1&page_size=20")
    assert r2.status_code == 200
    items = r2.json()["data"]["items"]
    assert any(x["id"] == kb_id for x in items)

