def test_get_conversation_not_found(auth_client):
    r = auth_client.get("/api/v1/conversations/not_exist")
    assert r.status_code == 404
    body = r.json()
    assert body["error_code"] == "CONVERSATION_NOT_FOUND"


def test_list_conversations_kb_not_found(auth_client):
    r = auth_client.get("/api/v1/knowledge-bases/not_exist/conversations?page=1&page_size=20")
    assert r.status_code == 404
    body = r.json()
    assert body["error_code"] == "KB_NOT_FOUND"

