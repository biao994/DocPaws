def test_chat_kb_not_found(auth_client):
    r = auth_client.post(
        "/api/v1/chat",
        json={
            "kb_id": "not_exist",
            "question": "你好",
            "conversation_id": None,
        },
    )
    assert r.status_code == 404
    body = r.json()
    # 业务异常统一在全局 handler 直接返回标准错误体（不再包一层 detail）
    assert body["error_code"] == "KB_NOT_FOUND"


def test_chat_index_not_ready_returns_409(auth_client, db_session):
    # 有文档/切片但尚未有 active 索引产物 → INDEX_NOT_READY
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    from docpaws.domain.models.document import Document, Chunk

    doc = Document(kb_id=kb_id, title="t1", content="c")
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    db_session.add(Chunk(document_id=doc.id, content="hello chunk"))
    db_session.commit()

    r2 = auth_client.post(
        "/api/v1/chat",
        json={
            "kb_id": kb_id,
            "question": "你好",
            "conversation_id": None,
        },
    )
    assert r2.status_code == 409
    body = r2.json()
    assert body["error_code"] == "INDEX_NOT_READY"

