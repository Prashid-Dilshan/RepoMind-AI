import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("langchain_core")

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from utils import indexer, registry  # noqa: E402

REPO_ID = "abcdef0123"


@pytest.fixture()
def client():
    with TestClient(main.app) as c:
        for row in registry.list_all():
            registry.delete(row["repo_id"])
        yield c


def test_health_and_config(client):
    assert client.get("/api/health").json() == {"ok": True}
    cfg = client.get("/api/config").json()
    assert cfg["auth_required"] is False
    assert cfg["openai_key_set"] is True


def test_security_headers_are_present(client):
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_empty_list_and_unknown_repo(client):
    assert client.get("/api/repos").json() == {"repos": []}
    assert client.get(f"/api/repos/{REPO_ID}").status_code == 404
    assert client.delete(f"/api/repos/{REPO_ID}").status_code == 404


def test_repo_id_must_look_like_an_id(client):
    assert client.get("/api/repos/..%2F..%2Fetc").status_code in (404, 422)
    assert client.get("/api/repos/NOT-AN-ID").status_code == 422


def test_invalid_url_is_a_400_with_a_helpful_message(client):
    response = client.post("/api/repos", json={"repo_url": "https://gitlab.com/a/b"})
    assert response.status_code == 400
    assert "GitHub" in response.json()["detail"]


def test_indexing_starts_in_the_background(client, monkeypatch):
    monkeypatch.setattr(indexer, "fetch_repo_info", lambda owner, name: {
        "full_name": "Pallets/click", "description": "CLI toolkit", "language": "Python",
        "stars": 10, "default_branch": "main",
    })
    submitted = []
    monkeypatch.setattr(indexer._executor, "submit", lambda fn, *a: submitted.append(a))

    response = client.post("/api/repos", json={"repo_url": "https://github.com/pallets/click"})
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "processing"
    assert body["stage"] == "queued"
    assert body["name"] == "Pallets/click"
    assert len(submitted) == 1

    # Asking again while it is processing must not start a second job.
    client.post("/api/repos", json={"repo_url": "https://github.com/pallets/click"})
    assert len(submitted) == 1
    assert len(client.get("/api/repos").json()["repos"]) == 1


def test_deleting_a_repo_that_is_processing_is_refused(client):
    registry.upsert(REPO_ID, url="u", name="o/r", status="processing")
    assert client.delete(f"/api/repos/{REPO_ID}").status_code == 400


def test_asking_before_indexing_is_a_409(client):
    response = client.post("/api/query/stream", json={"question": "hi", "repo_id": REPO_ID})
    assert response.status_code == 409


def test_question_validation(client):
    assert client.post("/api/query", json={"question": "", "repo_id": REPO_ID}).status_code == 422
    assert client.post("/api/query", json={"question": "hi", "repo_id": "../x"}).status_code == 422


def test_streaming_endpoint_sends_sources_tokens_and_done(client, monkeypatch):
    registry.upsert(REPO_ID, url="u", name="o/r", status="completed")
    monkeypatch.setattr(main, "has_vector_store", lambda repo_id: True)

    def fake_stream(question, repo_id, history, repo):
        yield {"type": "sources", "sources": [{"path": "a.py"}]}
        yield {"type": "token", "text": "Hel"}
        yield {"type": "token", "text": "lo"}

    monkeypatch.setattr(main, "stream_answer", fake_stream)
    response = client.post("/api/query/stream", json={"question": "hi", "repo_id": REPO_ID})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [line for line in response.text.split("\n\n") if line]
    assert events[0].startswith('data: {"type": "sources"')
    assert events[-1] == 'data: {"type": "done"}'
    assert len(events) == 4


def test_access_key_protects_private_routes_only(client, monkeypatch):
    monkeypatch.setattr("utils.config.ACCESS_KEY", "s3cret")
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/config").json()["auth_required"] is True
    assert client.get("/api/repos").status_code == 401
    assert client.get("/api/repos", headers={"X-Access-Key": "wrong"}).status_code == 401
    assert client.get("/api/repos", headers={"X-Access-Key": "s3cret"}).status_code == 200
    assert client.get("/api/auth/check", headers={"X-Access-Key": "s3cret"}).json() == {"ok": True}
