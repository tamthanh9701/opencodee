import pytest
from pathlib import Path

from claw_system.models import PipelineStatus
from claw_system.state import StateStore
from claw_system.router import PipelineRouter


@pytest.fixture
async def router(tmp_path: Path):
    db_path = tmp_path / "router_test.db"
    store = StateStore(db_path)
    r = PipelineRouter(state_store=store)
    yield r
    await store.close()


async def test_run_pipeline_success(router: PipelineRouter):
    state = await router.run("https://example.com")
    assert state.status == PipelineStatus.COMPLETED
    assert state.url == "https://example.com"
    assert state.collector_output is not None
    assert state.analyst_output is not None
    assert state.fig_output is not None


async def test_run_pipeline_creates_state(router: PipelineRouter):
    state = await router.run("https://test.com")
    assert state.id is not None
    assert state.created_at is not None


async def test_resume_completed_pipeline(router: PipelineRouter):
    state = await router.run("https://example.com")
    assert state.status == PipelineStatus.COMPLETED
    resumed = await router.resume(state.id)
    assert resumed.status == PipelineStatus.COMPLETED


async def test_resume_nonexistent_pipeline(router: PipelineRouter):
    with pytest.raises(ValueError, match="not found"):
        await router.resume("nonexistent-id")


async def test_pipeline_state_persists(router: PipelineRouter):
    state = await router.run("https://example.com")
    fetched = await router.state_store.get(state.id)
    assert fetched is not None
    assert fetched.status == PipelineStatus.COMPLETED