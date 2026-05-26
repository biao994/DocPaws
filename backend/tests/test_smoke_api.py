
def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_root_ok(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "running"
    assert body.get("docs") == "/docs"

