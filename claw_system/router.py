import time
from typing import Any

import structlog

from claw_collector.models import CollectedPage
from claw_analyst.models import AnalysisResult
from claw_fig.models import FigmaCreateResult
from claw_system.models import PipelineState, PipelineStatus, TaskResult
from claw_system.recovery import retry, MaxRetriesExceeded
from claw_system.state import StateStore
from claw_system.validator import validate_output

logger = structlog.get_logger(__name__)

STEP_MAP = {
    PipelineStatus.COLLECTING: "collector",
    PipelineStatus.ANALYZING: "analyst",
    PipelineStatus.BUILDING_FIG: "fig",
}


class PipelineRouter:
    def __init__(self, state_store: StateStore | None = None) -> None:
        self.state_store = state_store or StateStore()
        self._crew = None

    def _get_crew(self):
        if self._crew is None:
            from claw_system.crew import ClawCrew
            self._crew = ClawCrew()
        return self._crew

    async def _mock_collect(self, url: str) -> CollectedPage:
        logger.info("mock_collect", url=url)
        return CollectedPage(url=url, viewport="desktop")

    async def _mock_analyze(self, collected: CollectedPage) -> AnalysisResult:
        logger.info("mock_analyze", url=collected.url)
        return AnalysisResult()

    async def _mock_build_fig(self, analysis: AnalysisResult) -> FigmaCreateResult:
        logger.info("mock_build_fig")
        return FigmaCreateResult(
            file_key="mock_key",
            file_url="https://figma.com/file/mock_key",
        )

    async def _run_step(
        self,
        step_name: str,
        next_status: PipelineStatus,
        state: PipelineState,
        step_fn,
        output_field: str,
        schema_cls: type,
    ) -> PipelineState:
        logger.info("pipeline_step_start", step=step_name, pipeline_id=state.id)
        state = await self.state_store.update(
            state.id, status=next_status.value
        ) or state

        start = time.monotonic()
        try:
            raw_result = await retry(step_fn)
            elapsed_ms = int((time.monotonic() - start) * 1000)

            if isinstance(raw_result, dict):
                result = validate_output(schema_cls, raw_result)
            else:
                result = TaskResult(status="success", data=raw_result)

            if result.status == "error":
                raise ValueError(f"Validation failed: {result.error}")

            await self.state_store.update(
                state.id,
                **{output_field: raw_result.model_dump() if hasattr(raw_result, "model_dump") else raw_result},
            )
            logger.info(
                "pipeline_step_done",
                step=step_name,
                pipeline_id=state.id,
                elapsed_ms=elapsed_ms,
            )
            state = await self.state_store.get(state.id)
            return state or state

        except MaxRetriesExceeded as e:
            logger.error(
                "pipeline_step_failed",
                step=step_name,
                pipeline_id=state.id,
                error=str(e),
            )
            await self.state_store.update(
                state.id,
                status=PipelineStatus.FAILED.value,
                error_message=f"{step_name} failed: {e}",
            )
            raise
        except Exception as e:
            logger.error(
                "pipeline_step_error",
                step=step_name,
                pipeline_id=state.id,
                error=str(e),
            )
            await self.state_store.update(
                state.id,
                status=PipelineStatus.FAILED.value,
                error_message=f"{step_name} error: {e}",
            )
            raise

    async def run(self, url: str) -> PipelineState:
        logger.info("pipeline_run_start", url=url)
        state = await self.state_store.create(url)

        collected = await self._run_step(
            "collect",
            PipelineStatus.COLLECTING,
            state,
            lambda: self._mock_collect(url),
            "collector_output",
            CollectedPage,
        )

        if collected.status == PipelineStatus.FAILED:
            return collected

        analyzed = await self._run_step(
            "analyze",
            PipelineStatus.ANALYZING,
            collected,
            lambda: self._mock_analyze(CollectedPage.model_validate(collected.collector_output)),
            "analyst_output",
            AnalysisResult,
        )

        if analyzed.status == PipelineStatus.FAILED:
            return analyzed

        result = await self._run_step(
            "build_fig",
            PipelineStatus.BUILDING_FIG,
            analyzed,
            lambda: self._mock_build_fig(AnalysisResult.model_validate(analyzed.analyst_output)),
            "fig_output",
            FigmaCreateResult,
        )

        if result.status != PipelineStatus.FAILED:
            result = await self.state_store.update(
                result.id, status=PipelineStatus.COMPLETED.value
            ) or result

        logger.info("pipeline_run_done", pipeline_id=result.id, status=result.status)
        return result

    async def resume(self, pipeline_id: str) -> PipelineState:
        state = await self.state_store.get(pipeline_id)
        if state is None:
            raise ValueError(f"Pipeline {pipeline_id} not found")

        logger.info("pipeline_resume", pipeline_id=pipeline_id, status=state.status)

        if state.status == PipelineStatus.COMPLETED:
            logger.info("pipeline_already_completed", pipeline_id=pipeline_id)
            return state

        if state.status == PipelineStatus.FAILED:
            logger.info("pipeline_retrying_from_failed", pipeline_id=pipeline_id)

        if state.status in (PipelineStatus.PENDING, PipelineStatus.COLLECTING) or state.collector_output is None:
            return await self.run(state.url)

        if state.status in (PipelineStatus.ANALYZING,) or state.analyst_output is None:
            collected = CollectedPage.model_validate(state.collector_output)
            analyzed = await self._run_step(
                "analyze",
                PipelineStatus.ANALYZING,
                state,
                lambda: self._mock_analyze(collected),
                "analyst_output",
                AnalysisResult,
            )
            if analyzed.status == PipelineStatus.FAILED:
                return analyzed
            result = await self._run_step(
                "build_fig",
                PipelineStatus.BUILDING_FIG,
                analyzed,
                lambda: self._mock_build_fig(AnalysisResult.model_validate(analyzed.analyst_output)),
                "fig_output",
                FigmaCreateResult,
            )
            if result.status != PipelineStatus.FAILED:
                result = await self.state_store.update(result.id, status=PipelineStatus.COMPLETED.value) or result
            return result

        if state.status in (PipelineStatus.BUILDING_FIG,) or state.analyst_output is not None:
            analysis = AnalysisResult.model_validate(state.analyst_output)
            result = await self._run_step(
                "build_fig",
                PipelineStatus.BUILDING_FIG,
                state,
                lambda: self._mock_build_fig(analysis),
                "fig_output",
                FigmaCreateResult,
            )
            if result.status != PipelineStatus.FAILED:
                result = await self.state_store.update(result.id, status=PipelineStatus.COMPLETED.value) or result
            return result

        return state