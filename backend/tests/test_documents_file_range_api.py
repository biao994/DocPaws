import io


def _upload_one_pdf(auth_client) -> tuple[str, str]:
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb_range", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    # 造一个足够长的“看起来像 PDF”的字节串，方便测 range
    payload = b"%PDF-1.4\n" + (b"x" * 4096) + b"\n%%EOF\n"
    r1 = auth_client.post(
        f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&folder_path=folder1",
        files={"file": ("a.pdf", io.BytesIO(payload), "application/pdf")},
    )
    assert r1.status_code == 202, r1.text
    doc_id = r1.json()["data"]["document_id"]
    return doc_id, payload.decode("latin1", errors="ignore")  # only for length hint


def test_get_document_file_supports_range_first_bytes(auth_client):
    doc_id, _ = _upload_one_pdf(auth_client)

    r = auth_client.get(
        f"/api/v1/documents/{doc_id}/file",
        headers={"Range": "bytes=0-9"},
    )
    assert r.status_code == 206
    assert r.headers.get("accept-ranges") == "bytes"
    assert r.headers.get("content-range", "").startswith("bytes 0-9/")
    assert r.headers.get("content-length") == "10"
    assert len(r.content) == 10


def test_get_document_file_supports_range_suffix(auth_client):
    doc_id, _ = _upload_one_pdf(auth_client)

    r = auth_client.get(
        f"/api/v1/documents/{doc_id}/file",
        headers={"Range": "bytes=-5"},
    )
    assert r.status_code == 206
    assert r.headers.get("accept-ranges") == "bytes"
    assert r.headers.get("content-range", "").startswith("bytes ")
    assert r.headers.get("content-length") == "5"
    assert len(r.content) == 5


def test_get_document_file_range_invalid_returns_416(auth_client):
    doc_id, _ = _upload_one_pdf(auth_client)

    r = auth_client.get(
        f"/api/v1/documents/{doc_id}/file",
        headers={"Range": "bytes=999999999-1000000000"},
    )
    assert r.status_code == 416

