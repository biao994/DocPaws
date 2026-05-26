import io

from sqlmodel import select


def test_delete_document_cascade_removes_db_rows(auth_client, db_session):
    # create KB
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    # upload doc
    pdf = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    r1 = auth_client.post(
        f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&folder_path=folder1",
        files={"file": ("a.pdf", pdf, "application/pdf")},
    )
    assert r1.status_code == 202
    doc_id = r1.json()["data"]["document_id"]
    job_id = r1.json()["data"]["job_id"]

    # sanity: rows exist
    from docpaws.domain.models.document import Document, KbFile, FileObject
    from docpaws.domain.models.index import IndexJob

    doc = db_session.get(Document, doc_id)
    assert doc is not None
    kb_file_id = doc.kb_file_id
    assert kb_file_id
    kb_file = db_session.get(KbFile, kb_file_id)
    assert kb_file is not None
    file_obj = db_session.get(FileObject, kb_file.file_object_id)
    assert file_obj is not None
    file_obj_id = file_obj.id
    assert db_session.get(IndexJob, job_id) is not None

    # delete via API
    r_del = auth_client.delete(f"/api/v1/documents/{doc_id}")
    assert r_del.status_code == 200
    assert r_del.json()["data"]["status"] == "deleted"

    # DB rows should be removed
    # API 请求使用的是另一个 session，这里需要清理 identity map
    db_session.expire_all()
    assert db_session.get(Document, doc_id) is None
    # KB 级索引任务不按单文档级联删除
    assert db_session.get(IndexJob, job_id) is not None
    assert db_session.get(KbFile, kb_file_id) is None
    assert db_session.get(FileObject, file_obj_id) is None

