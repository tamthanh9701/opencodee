import pytest
from pathlib import Path

from claw_system.models import PipelineStatus
from claw_system.state import StateStore


@pytest.fixture
async def store(tmp_path: Path):
    db_path = tmp_path / "test.db"
    s = StateStore(db_path)
    yield s
    await s.close()


async def test_create_pipeline(store: StateStore):
    state = await store.create("https://example.com")
    assert state.url == "https://example.com"
    assert state.status == PipelineStatus.PENDING
    assert state.id is not None


async def test_get_pipeline(store: StateStore):
    created = await store.create("https://example.com")
    fetched = await store.get(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.url == created.url


async def test_get_nonexistent(store: StateStore):
    result = await store.get("nonexistent-id")
    assert result is None


async def test_update_pipeline(store: StateStore):
    state = await store.create("https://example.com")
    updated = await store.update(state.id, status=PipelineStatus.COLLECTING.value)
    assert updated is not None
    assert updated.status == PipelineStatus.COLLECTING


async def test_update_with_output(store: StateStore):
    state = await store.create("https://example.com")
    updated = await store.update(
        state.id,
        collector_output={"url": "https://example.com", "elements": []},
    )
    assert updated is not None
    assert updated.collector_output == {"url": "https://example.com", "elements": []}


async def test_list_by_status(store: StateStore):
    s1 = await store.create("https://a.com")
    s2 = await store.create("https://b.com")
    await store.update(s1.id, status=PipelineStatus.COLLECTING.value)

    pending = await store.list_by_status(PipelineStatus.PENDING)
    assert len(pending) == 1
    assert pending[0].id == s2.id

    collecting = await store.list_by_status(PipelineStatus.COLLECTING)
    assert len(collecting) == 1
    assert collecting[0].id == s1.id


async def test_get_latest_pending(store: StateStore):
    await store.create("https://a.com")
    s2 = await store.create("https://b.com")
    latest = await store.get_latest_pending()
    assert latest is not None
    assert latest.id == s2.id


async def test_get_latest_pending_with_collecting(store: StateStore):
    await store.create("https://a.com")
    s2 = await store.create("https://b.com")
    await store.update(s2.id, status=PipelineStatus.COLLECTING.value)
    latest = await store.get_latest_pending()
    assert latest is not None
    assert latest.status in (PipelineStatus.PENDING, PipelineStatus.COLLECTING)


async def test_get_latest_pending_empty(store: StateStore):
    result = await store.get_latest_pending()
    assert result is None


async def test_delete_pipeline(store: StateStore):
    state = await store.create("https://example.com")
    deleted = await store.delete(state.id)
    assert deleted is True
    fetched = await store.get(state.id)
    assert fetched is None


async def test_delete_nonexistent(store: StateStore):
    deleted = await store.delete("nonexistent")
    assert deleted is False