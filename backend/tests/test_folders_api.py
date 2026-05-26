import io


def _create_kb(auth_client):
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb-folders", "description": ""},
    )
    assert r.status_code == 200
    return r.json()["data"]["id"]


def test_create_empty_folder_and_rename(auth_client):
    kb_id = _create_kb(auth_client)
    r = auth_client.post(
        f"/api/v1/knowledge-bases/{kb_id}/folders",
        json={"name": "我的资料"},
    )
    assert r.status_code == 200
    folder_id = r.json()["data"]["id"]
    assert r.json()["data"]["name"] == "我的资料"
    assert r.json()["data"]["path"] == "我的资料"

    r2 = auth_client.patch(
        f"/api/v1/knowledge-bases/{kb_id}/folders/{folder_id}",
        json={"name": "资料库"},
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["name"] == "资料库"


def test_upload_with_folder_id_and_rename_document(auth_client):
    kb_id = _create_kb(auth_client)
    r_folder = auth_client.post(
        f"/api/v1/knowledge-bases/{kb_id}/folders",
        json={"name": "fp1"},
    )
    folder_id = r_folder.json()["data"]["id"]

    pdf_bytes = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    files = {"file": ("a.pdf", pdf_bytes, "application/pdf")}
    r1 = auth_client.post(
        f"/api/v1/documents?kb_id={kb_id}&on_conflict=create&folder_id={folder_id}",
        files=files,
    )
    assert r1.status_code == 202
    doc_id = r1.json()["data"]["document_id"]

    r_list = auth_client.get(f"/api/v1/knowledge-bases/{kb_id}/documents?page=1&page_size=20")
    item = next(x for x in r_list.json()["data"]["items"] if x["id"] == doc_id)
    assert item["folder_id"] == folder_id
    assert item["folder_path"] == "fp1"

    r_patch = auth_client.patch(
        f"/api/v1/documents/{doc_id}",
        json={"title": "报告"},
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["data"]["title"] == "报告"
