import io


def test_list_documents_kb_not_found(auth_client):
    r = auth_client.get("/api/v1/knowledge-bases/not_exist/documents")
    assert r.status_code in (404, 422)


def test_upload_reject_non_pdf(auth_client):
    # 先建 KB
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    kb_id = r.json()["data"]["id"]

    fake_txt = io.BytesIO(b"hello")
    files = {"file": ("a.txt", fake_txt, "text/plain")}
    r2 = auth_client.post(f"/api/v1/documents?kb_id={kb_id}", files=files)
    assert r2.status_code in (400, 422)


def test_upload_name_conflict_returns_409_with_details(auth_client):
    # 先建 KB
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    # 上传一个“看起来像 PDF”的文件（服务只校验扩展名/MIME，不需要真实解析）
    pdf_bytes = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    files = {"file": ("a.pdf", pdf_bytes, "application/pdf")}
    r1 = auth_client.post(f"/api/v1/documents?kb_id={kb_id}&on_conflict=create", files=files)
    assert r1.status_code == 202

    # 再上传同名同路径，触发 NAME_CONFLICT
    pdf_bytes2 = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    files2 = {"file": ("a.pdf", pdf_bytes2, "application/pdf")}
    r2 = auth_client.post(f"/api/v1/documents?kb_id={kb_id}&on_conflict=create", files=files2)
    assert r2.status_code == 409
    body = r2.json()
    assert body["error_code"] == "NAME_CONFLICT"
    assert isinstance(body.get("details"), dict)
    assert "existing_document_id" in body["details"]
    assert body["details"].get("incoming_filename") == "a.pdf"


def test_upload_same_title_different_folder_path_allowed(auth_client):
    # 先建 KB
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    pdf_bytes = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    files = {"file": ("a.pdf", pdf_bytes, "application/pdf")}
    r1 = auth_client.post(f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&folder_path=folder1", files=files)
    assert r1.status_code == 202

    # 同 KB、同文件名，但不同 folder_path：应允许
    pdf_bytes2 = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    files2 = {"file": ("a.pdf", pdf_bytes2, "application/pdf")}
    r2 = auth_client.post(f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&folder_path=folder2", files=files2)
    assert r2.status_code == 202


def test_upload_same_title_same_folder_path_conflict_409(auth_client):
    # 先建 KB
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    pdf_bytes = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    files = {"file": ("a.pdf", pdf_bytes, "application/pdf")}
    r1 = auth_client.post(f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&folder_path=folder1", files=files)
    assert r1.status_code == 202

    pdf_bytes2 = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    files2 = {"file": ("a.pdf", pdf_bytes2, "application/pdf")}
    r2 = auth_client.post(f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&folder_path=folder1", files=files2)
    assert r2.status_code == 409
    body = r2.json()
    assert body["error_code"] == "NAME_CONFLICT"
    assert isinstance(body.get("details"), dict)


def test_list_documents_includes_folder_path_and_filter_works(auth_client):
    # 先建 KB
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    pdf_bytes = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    files = {"file": ("a.pdf", pdf_bytes, "application/pdf")}
    r1 = auth_client.post(f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&folder_path=folder1", files=files)
    assert r1.status_code == 202

    pdf_bytes2 = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    files2 = {"file": ("b.pdf", pdf_bytes2, "application/pdf")}
    r2 = auth_client.post(f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&folder_path=folder2", files=files2)
    assert r2.status_code == 202

    # 列表应返回 folder_path 字段
    r_list = auth_client.get(f"/api/v1/knowledge-bases/{kb_id}/documents?page=1&page_size=20")
    assert r_list.status_code == 200
    items = r_list.json()["data"]["items"]
    assert all("folder_path" in x for x in items)
    assert {x["folder_path"] for x in items} >= {"folder1", "folder2"}

    # folder_path 过滤
    r_f = auth_client.get(f"/api/v1/knowledge-bases/{kb_id}/documents?page=1&page_size=20&folder_path=folder1")
    assert r_f.status_code == 200
    items_f = r_f.json()["data"]["items"]
    assert items_f, "filter should return at least one item"
    assert all(x["folder_path"] == "folder1" for x in items_f)


def test_list_documents_status_filter_ready(auth_client):
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb_filter", "description": ""},
    )
    kb_id = r.json()["data"]["id"]

    pdf_bytes = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    files = {"file": ("filter.pdf", pdf_bytes, "application/pdf")}
    up = auth_client.post(f"/api/v1/documents?kb_id={kb_id}&on_conflict=create", files=files)
    assert up.status_code == 202

    r_all = auth_client.get(f"/api/v1/knowledge-bases/{kb_id}/documents?page=1&page_size=20")
    assert r_all.status_code == 200
    all_items = r_all.json()["data"]["items"]
    assert len(all_items) >= 1

    r_ready = auth_client.get(
        f"/api/v1/knowledge-bases/{kb_id}/documents?page=1&page_size=20&status=ready",
    )
    assert r_ready.status_code == 200
    ready_items = r_ready.json()["data"]["items"]
    assert all(x["status"] == "ready" for x in ready_items)


def test_upload_idempotency_key_returns_same_job(auth_client):
    # 先建 KB
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    key = "req-1"
    pdf_bytes = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    files = {"file": ("a.pdf", pdf_bytes, "application/pdf")}
    r1 = auth_client.post(f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&idempotency_key={key}", files=files)
    assert r1.status_code == 202
    job1 = r1.json()["data"]["job_id"]

    pdf_bytes2 = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    # 同一个 idempotency_key，即使其它参数不同，也应返回同一个 job（幂等兜底）
    files2 = {"file": ("b.pdf", pdf_bytes2, "application/pdf")}
    r2 = auth_client.post(f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&idempotency_key={key}&folder_path=folder2", files=files2)
    assert r2.status_code == 202
    job2 = r2.json()["data"]["job_id"]
    assert job1 == job2


def test_upload_auto_rename_creates_second_doc(auth_client):
    import io

    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    pdf1 = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    r1 = auth_client.post(
        f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&folder_path=folder1",
        files={"file": ("a.pdf", pdf1, "application/pdf")},
    )
    assert r1.status_code == 202

    # 再上传同名同路径，但用 auto_rename：应返回 202，并标记 auto_renamed
    pdf2 = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    r2 = auth_client.post(
        f"/api/v1/documents?kb_id={kb_id}&on_conflict=auto_rename&folder_path=folder1",
        files={"file": ("a.pdf", pdf2, "application/pdf")},
    )
    assert r2.status_code == 202
    assert r2.json()["data"].get("auto_renamed") is True

    # 列表应该至少有 2 个文档
    r_list = auth_client.get(f"/api/v1/knowledge-bases/{kb_id}/documents?page=1&page_size=20&folder_path=folder1")
    assert r_list.status_code == 200
    assert r_list.json()["data"]["total"] >= 2


def test_upload_replace_reuses_document_id(auth_client):
    import io

    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    pdf1 = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    r1 = auth_client.post(
        f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&folder_path=folder1",
        files={"file": ("a.pdf", pdf1, "application/pdf")},
    )
    assert r1.status_code == 202
    doc_id = r1.json()["data"]["document_id"]

    # replace：指定 replace_document_id，应复用 document_id
    pdf2 = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    r2 = auth_client.post(
        f"/api/v1/documents?kb_id={kb_id}&on_conflict=replace&replace_document_id={doc_id}&folder_path=folder1",
        files={"file": ("a.pdf", pdf2, "application/pdf")},
    )
    assert r2.status_code == 202
    assert r2.json()["data"]["document_id"] == doc_id
    assert r2.json()["data"].get("is_replace") is True


def test_replace_same_file_object_keeps_ready(auth_client, db_session):
    """同一 FileObject 替换（内容未变）：不应把 ready 降级为 draft。"""
    import io

    from docpaws.domain.models.document import Document

    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    r1 = auth_client.post(
        f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&folder_path=folder1",
        files={"file": ("a.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert r1.status_code == 202
    doc_id = r1.json()["data"]["document_id"]

    db_session.expire_all()
    doc = db_session.get(Document, doc_id)
    assert doc is not None
    doc.status = "ready"
    db_session.add(doc)
    db_session.commit()

    r2 = auth_client.post(
        f"/api/v1/documents?kb_id={kb_id}&on_conflict=replace&replace_document_id={doc_id}&folder_path=folder1",
        files={"file": ("a.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert r2.status_code == 202
    assert r2.json()["data"].get("is_duplicate") is True

    db_session.expire_all()
    doc_after = db_session.get(Document, doc_id)
    assert doc_after is not None
    assert doc_after.status == "ready"


def test_upload_same_content_deduplicates_file_object(auth_client, db_session):
    from sqlmodel import select

    # create KB
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    # upload #1
    pdf_payload = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    r1 = auth_client.post(
        f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&folder_path=folder1",
        files={"file": ("a.pdf", io.BytesIO(pdf_payload), "application/pdf")},
    )
    assert r1.status_code == 202
    data1 = r1.json()["data"]
    assert data1.get("is_duplicate") is False

    # upload #2: same bytes, different filename (avoid name conflict), should deduplicate by sha256
    r2 = auth_client.post(
        f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&folder_path=folder1",
        files={"file": ("b.pdf", io.BytesIO(pdf_payload), "application/pdf")},
    )
    assert r2.status_code == 202
    data2 = r2.json()["data"]
    assert data2.get("sha256") == data1.get("sha256")
    assert data2.get("is_duplicate") is True

    # DB assert: both documents should reference the SAME FileObject
    from docpaws.domain.models.document import Document, KbFile, FileObject

    db_session.expire_all()
    doc1 = db_session.get(Document, data1["document_id"])
    doc2 = db_session.get(Document, data2["document_id"])
    assert doc1 and doc2
    kb_file1 = db_session.get(KbFile, doc1.kb_file_id)
    kb_file2 = db_session.get(KbFile, doc2.kb_file_id)
    assert kb_file1 and kb_file2
    assert kb_file1.file_object_id == kb_file2.file_object_id

    # Only one FileObject row should exist with that sha256
    fos = db_session.exec(select(FileObject).where(FileObject.sha256 == data1["sha256"])).all()
    assert len(fos) == 1
    assert fos[0].object_key
    assert fos[0].storage_provider == "minio"
    assert fos[0].object_key.startswith("u/")


def test_batch_upload_documents_two_files(auth_client):
    import io
    import json

    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    r2 = auth_client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/batch?on_conflict=create",
        files=[
            ("files", ("a.pdf", io.BytesIO(pdf), "application/pdf")),
            ("files", ("b.pdf", io.BytesIO(pdf), "application/pdf")),
        ],
    )
    assert r2.status_code == 202, r2.text
    data = r2.json()["data"]
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["document_id"] != data["items"][1]["document_id"]
    assert data["job_id"]

    r3 = auth_client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/batch?on_conflict=create&folder_path=fp1",
        data={"relative_paths": json.dumps(["fp1/c.pdf", "fp1/d.pdf"])},
        files=[
            ("files", ("c.pdf", io.BytesIO(pdf), "application/pdf")),
            ("files", ("d.pdf", io.BytesIO(pdf), "application/pdf")),
        ],
    )
    assert r3.status_code == 202, r3.text
    d3 = r3.json()["data"]
    assert d3["total"] == 2
    assert all(i.get("folder_path") == "fp1" for i in d3["items"])


def test_upload_reject_illegal_folder_path(auth_client):
    # create KB
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    pdf = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    r_bad = auth_client.post(
        f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&folder_path=../evil",
        files={"file": ("a.pdf", pdf, "application/pdf")},
    )
    assert r_bad.status_code in (400, 422)


def test_upload_replace_document_not_found_returns_404(auth_client):
    # create KB
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    pdf = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    r_bad = auth_client.post(
        f"/api/v1/documents?kb_id={kb_id}&on_conflict=replace&replace_document_id=not_exist",
        files={"file": ("a.pdf", pdf, "application/pdf")},
    )
    assert r_bad.status_code == 404
