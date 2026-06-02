def test_get_document_thumbnail_returns_webp(auth_client, db_session, monkeypatch):
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb-thumb", "description": ""},
    )
    kb_id = r.json()["data"]["id"]

    from docpaws.domain.models.document import Document, FileObject, KbFile

    fo = FileObject(
        storage_provider="minio",
        object_key="u/test/doc.pdf",
        sha256="abc123thumb",
        size_bytes=100,
        file_type="pdf",
    )
    db_session.add(fo)
    db_session.flush()

    kb_file = KbFile(
        kb_id=kb_id,
        file_object_id=fo.id,
        original_filename="a.pdf",
        uploaded_by="u1",
        status="active",
    )
    db_session.add(kb_file)
    db_session.flush()

    doc = Document(
        kb_id=kb_id,
        kb_file_id=kb_file.id,
        title="a",
        status="ready",
        thumbnail_key="thumbs/test-doc.webp",
    )
    db_session.add(doc)
    db_session.commit()

    fake_webp = b"RIFFxxxxWEBPVP8 "

    def fake_head_meta(object_key: str):
        assert object_key == "thumbs/test-doc.webp"
        return {"content_type": "image/webp", "content_length": len(fake_webp), "etag": "etag1"}

    def fake_stream_get(object_key: str, **kwargs):
        assert object_key == "thumbs/test-doc.webp"
        return iter([fake_webp]), {"content_length": len(fake_webp)}

    monkeypatch.setattr("docpaws.api.routers.documents.head_meta", fake_head_meta)
    monkeypatch.setattr("docpaws.api.routers.documents.stream_get", fake_stream_get)

    resp = auth_client.get(f"/api/v1/documents/{doc.id}/thumbnail")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/webp")
    assert "max-age=86400" in resp.headers.get("cache-control", "")
    assert resp.content == fake_webp


def test_get_document_thumbnail_not_ready_404(auth_client, db_session):
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb-no-thumb", "description": ""},
    )
    kb_id = r.json()["data"]["id"]

    from docpaws.domain.models.document import Document, FileObject, KbFile

    fo = FileObject(
        storage_provider="minio",
        object_key="u/test/doc2.pdf",
        sha256="abc123thumb2",
        size_bytes=100,
        file_type="pdf",
    )
    db_session.add(fo)
    db_session.flush()

    kb_file = KbFile(
        kb_id=kb_id,
        file_object_id=fo.id,
        original_filename="b.pdf",
        uploaded_by="u1",
        status="active",
    )
    db_session.add(kb_file)
    db_session.flush()

    doc = Document(kb_id=kb_id, kb_file_id=kb_file.id, title="b", status="draft")
    db_session.add(doc)
    db_session.commit()

    resp = auth_client.get(f"/api/v1/documents/{doc.id}/thumbnail")
    assert resp.status_code == 404
