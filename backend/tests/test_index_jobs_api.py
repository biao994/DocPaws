def test_get_index_job_not_found(auth_client):
    r = auth_client.get("/api/v1/index-jobs/not_exist")
    assert r.status_code == 404
    body = r.json()
    assert body["error_code"] == "JOB_NOT_FOUND"


def test_get_document_index_job_not_found(auth_client):
    """无效 document：归属校验先于「是否有 index job」，故为 DOCUMENT_NOT_FOUND。"""
    r = auth_client.get("/api/v1/index-jobs/documents/not_exist/index-job")
    assert r.status_code == 404
    body = r.json()
    assert body["error_code"] == "DOCUMENT_NOT_FOUND"

