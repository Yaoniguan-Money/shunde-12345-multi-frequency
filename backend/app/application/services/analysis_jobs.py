"""Single-process background analysis jobs exposed to the Demo HTTP API."""

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.application.services.analysis import (
    DEMO_MAX_WORK_ORDERS,
    DemoAnalysisOrchestrator,
)
from backend.app.config import Settings
from backend.app.domain.analysis_jobs import AnalysisJobView, UnderstandingRepository
from backend.app.domain.types import ProviderMode
from backend.app.infrastructure.ai.config import build_provider_plan
from backend.app.infrastructure.db.analysis import SQLAlchemyUnderstandingRepository

OrchestratorFactory = Callable[[], Awaitable[DemoAnalysisOrchestrator]]


class AnalysisJobService:
    """Queue bounded jobs and keep their durable state in the existing analysis tables."""

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        orchestrator_factory: OrchestratorFactory | None = None,
        repository: UnderstandingRepository | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._repository = repository or SQLAlchemyUnderstandingRepository(session_factory)
        if orchestrator_factory is None:

            async def create_orchestrator() -> DemoAnalysisOrchestrator:
                return await DemoAnalysisOrchestrator.create(settings, session_factory)

            self._orchestrator_factory = create_orchestrator
        else:
            self._orchestrator_factory = orchestrator_factory
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    async def submit(self, batch_id: UUID, max_work_orders: int) -> AnalysisJobView:
        if self._settings.ai_provider_mode is not ProviderMode.REMOTE:
            raise ValueError(
                "analysis jobs require explicit SHUNDE_AI_PROVIDER_MODE=remote; no local fallback"
            )
        if max_work_orders < 1 or max_work_orders > DEMO_MAX_WORK_ORDERS:
            raise ValueError(f"max_work_orders must be between 1 and {DEMO_MAX_WORK_ORDERS}")
        batch = await self._repository.get_batch_info(batch_id)
        if batch is None:
            raise LookupError(f"import batch not found: {batch_id}")
        if batch.status not in {"completed", "partial"}:
            raise ValueError(f"import batch is not ready for analysis: {batch.status}")
        sources = await self._repository.load_work_orders(batch_id, 0, max_work_orders)
        if not sources:
            raise ValueError("import batch contains no successful work orders")
        plan = build_provider_plan(self._settings)
        remote_llm = plan.remote_llm
        if remote_llm is None:
            raise ValueError("remote LLM provider is not configured")
        idempotency_key = (
            f"demo-analysis:{batch_id}:{max_work_orders}:{self._settings.analysis_pipeline_version}"
        )
        state = await self._repository.create_or_requeue(
            idempotency_key=idempotency_key,
            pipeline_version=self._settings.analysis_pipeline_version,
            schema_version=self._settings.analysis_schema_version,
            model_id=remote_llm.model_id,
            provider=remote_llm.provider,
            model_config_hash=remote_llm.config_hash(),
            total_rows=batch.total_rows,
            selected_rows=len(sources),
        )
        view = await self._repository.get_job_view(state.job_id)
        if view is None:
            raise LookupError(f"analysis job not found after creation: {state.job_id}")
        if view.status != "completed" and state.job_id not in self._tasks:
            self._tasks[state.job_id] = asyncio.create_task(
                self._execute(
                    state.job_id,
                    state.run_id,
                    batch_id,
                    max_work_orders,
                    idempotency_key,
                )
            )
        return view

    async def get(self, job_id: UUID) -> AnalysisJobView | None:
        return await self._repository.get_job_view(job_id)

    async def wait_for_completion(self, job_id: UUID) -> AnalysisJobView | None:
        task = self._tasks.get(job_id)
        if task is not None:
            await task
        return await self.get(job_id)

    async def shutdown(self) -> None:
        tasks = tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    async def _execute(
        self,
        job_id: UUID,
        run_id: UUID,
        batch_id: UUID,
        max_work_orders: int,
        idempotency_key: str,
    ) -> None:
        try:
            orchestrator = await self._orchestrator_factory()
            execution = await orchestrator.run_import_batch(
                batch_id,
                max_work_orders,
                idempotency_key=idempotency_key,
            )
            await self._repository.finish(
                job_id,
                run_id,
                {
                    "processed_rows": execution.processed_rows,
                    "event_count": execution.event_count,
                    "match_edge_count": execution.match_edge_count,
                    "cluster_count": execution.cluster_count,
                    "embeddings_written": execution.embeddings_written,
                },
            )
        except Exception as error:
            await self._repository.fail(job_id, run_id, "analysis_failed", str(error))
        finally:
            self._tasks.pop(job_id, None)
