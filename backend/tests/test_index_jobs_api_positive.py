import io


def test_upload_then_get_index_job_and_latest_job(auth_client):
    # create KB
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    # upload document (returns document_id + job_id)
    pdf_bytes = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    files = {"file": ("a.pdf", pdf_bytes, "application/pdf")}
    r1 = auth_client.post(f"/api/v1/documents?kb_id={kb_id}&on_conflict=create", files=files)
    assert r1.status_code == 202
    payload = r1.json()["data"]
    job_id = payload["job_id"]
    document_id = payload["document_id"]

    # query by job_id
    r_job = auth_client.get(f"/api/v1/index-jobs/{job_id}")
    assert r_job.status_code == 200
    data_job = r_job.json()["data"]
    assert data_job["id"] == job_id
    assert data_job["kb_id"] == kb_id
    assert "document_id" not in data_job

    # query latest job by document_id
    r_latest = auth_client.get(f"/api/v1/index-jobs/documents/{document_id}/index-job")
    assert r_latest.status_code == 200
    data_latest = r_latest.json()["data"]
    assert data_latest["id"] == job_id
    assert "document_id" not in data_latest
