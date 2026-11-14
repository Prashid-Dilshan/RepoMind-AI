import pytest

from utils import registry


@pytest.fixture(autouse=True)
def fresh_db():
    registry.init()
    for row in registry.list_all():
        registry.delete(row["repo_id"])
    yield


def test_upsert_creates_then_updates():
    registry.upsert("aaaaaaaaaa", url="u", name="o/r", status="processing", created_at=1.0)
    registry.upsert("aaaaaaaaaa", status="completed", files=3)
    row = registry.get("aaaaaaaaaa")
    assert row["status"] == "completed"
    assert row["files"] == 3
    assert row["name"] == "o/r"  # untouched fields survive a partial update


def test_unknown_columns_are_rejected():
    with pytest.raises(ValueError):
        registry.upsert("aaaaaaaaaa", nope=1)


def test_interrupted_jobs_are_marked_failed():
    registry.upsert("aaaaaaaaaa", status="processing")
    registry.upsert("bbbbbbbbbb", status="completed")
    registry.mark_interrupted()
    assert registry.get("aaaaaaaaaa")["status"] == "failed"
    assert "interrupted" in registry.get("aaaaaaaaaa")["error"]
    assert registry.get("bbbbbbbbbb")["status"] == "completed"


def test_evictable_returns_least_recently_used_but_never_processing():
    registry.upsert("aaaaaaaaaa", status="completed", last_used_at=1.0)
    registry.upsert("bbbbbbbbbb", status="completed", last_used_at=2.0)
    registry.upsert("cccccccccc", status="completed", last_used_at=3.0)
    registry.upsert("dddddddddd", status="processing", last_used_at=0.0)
    assert registry.evictable(keep=2) == ["aaaaaaaaaa"]
    assert registry.count_processing() == 1


def test_list_is_newest_first_and_delete_works():
    registry.upsert("aaaaaaaaaa", status="completed", last_used_at=1.0)
    registry.upsert("bbbbbbbbbb", status="completed", last_used_at=2.0)
    assert [r["repo_id"] for r in registry.list_all()] == ["bbbbbbbbbb", "aaaaaaaaaa"]
    registry.delete("bbbbbbbbbb")
    assert registry.get("bbbbbbbbbb") is None
