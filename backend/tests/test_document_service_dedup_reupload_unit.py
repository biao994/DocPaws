import io


def test_dedup_reupload_when_object_key_empty(monkeypatch, auth_client, db_session):
    """
    去重命中但 object_key 为空：应为该 FileObject 分配 key 并补传。
    """
    from docpaws.domain.models.document import FileObject
    from docpaws.usecases import document_service as svc

    # create KB
    r = auth_client.post("/api/v1/knowledge-bases", json={"name": "kb1", "description": ""})
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    # 先插入一个 sha256 命中的 FileObject，但 object_key 为空（模拟历史脏数据）
    fo = FileObject(
        id="fo_empty_key",
        storage_provider="minio",
        object_key="",
        sha256="sha_x",
        size_bytes=0,
        file_type="pdf",
    )
    db_session.add(fo)
    db_session.commit()

    monkeypatch.setattr(svc, "head_object", lambda _: False)
    monkeypatch.setattr(svc, "head_meta", lambda _: {"content_length": 0})

    uploaded = {}

    def _fake_upload(local_path: str, object_key: str, content_type: str | None = None):
        uploaded["key"] = object_key
        return {"etag": "x", "size": 12}

    monkeypatch.setattr(svc, "upload_file", _fake_upload)

    # monkeypatch sha256 计算结果，使其命中上面的 FileObject
    async def _fake_save_upload_to_temp_and_hash(_file):
        return (str(_file.file), "sha_x", 12)  # type: ignore[attr-defined]

    monkeypatch.setattr(svc.storage, "save_upload_to_temp_and_hash", _fake_save_upload_to_temp_and_hash)

    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    r2 = auth_client.post(
        f"/api/v1/documents?kb_id={kb_id}&on_conflict=create",
        files={"file": ("a.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert r2.status_code == 202, r2.text

    db_session.expire_all()
    fo2 = db_session.get(FileObject, "fo_empty_key")
    assert fo2 is not None
    assert fo2.object_key
    assert uploaded.get("key") == fo2.object_key


def test_dedup_reupload_when_object_zero_bytes(monkeypatch, auth_client, db_session):
    """
    去重命中且对象存在但 content_length=0：应补传覆盖。
    """
    from docpaws.domain.models.document import FileObject
    from docpaws.usecases import document_service as svc

    r = auth_client.post("/api/v1/knowledge-bases", json={"name": "kb1", "description": ""})
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    fo = FileObject(
        id="fo_zero",
        storage_provider="minio",
        object_key="u/x/kb/y/doc/fo_zero/a.pdf",
        sha256="sha_y",
        size_bytes=1,
        file_type="pdf",
    )
    db_session.add(fo)
    db_session.commit()

    monkeypatch.setattr(svc, "head_object", lambda _: True)
    monkeypatch.setattr(svc, "head_meta", lambda _: {"content_length": 0})

    uploaded = {"count": 0}

    def _fake_upload(local_path: str, object_key: str, content_type: str | None = None):
        uploaded["count"] += 1
        return {"etag": "x", "size": 12}

    monkeypatch.setattr(svc, "upload_file", _fake_upload)

    async def _fake_save_upload_to_temp_and_hash(_file):
        return (str(_file.file), "sha_y", 12)  # type: ignore[attr-defined]

    monkeypatch.setattr(svc.storage, "save_upload_to_temp_and_hash", _fake_save_upload_to_temp_and_hash)

    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    r2 = auth_client.post(
        f"/api/v1/documents?kb_id={kb_id}&on_conflict=create",
        files={"file": ("a.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert r2.status_code == 202, r2.text
    assert uploaded["count"] == 1

