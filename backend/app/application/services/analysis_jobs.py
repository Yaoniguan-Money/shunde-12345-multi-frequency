"""Single-process background analysis jobs exposed to the HTTP API.

WP2: 研判范围等于导入批次全部成功工单；不再接受 max_work_orders 或 selection_mode。
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.application.services.analysis import DemoAnalysisOrchestrator
from backend.app.application.services.provider_profiles import ProviderProfileService
from backend.app.config import Settings
from backend.app.domain.analysis_jobs import (
    AnalysisJobState,
    AnalysisJobView,
    FrozenScope,
    UnderstandingRepository,
)
from backend.app.domain.types import ProviderMode
from backend.app.infrastructure.ai.config import build_provider_plan
from backend.app.infrastructure.db.analysis import SQLAlchemyUnderstandingRepository

OrchestratorFactory = Callable[[], Awaitable[DemoAnalysisOrchestrator]]


class AnalysisJobService:
    """Queue full-batch jobs and keep their durable state in the analysis tables."""

    _ACTIVE_PIPELINE_VERSION = "understanding.v3"
    _ACTIVE_SCHEMA_VERSION = "understanding.v3"

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        orchestrator_factory: OrchestratorFactory | None = None,
        repository: UnderstandingRepository | None = None,
        provider_profiles: ProviderProfileService | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._repository = repository or SQLAlchemyUnderstandingRepository(session_factory)
        self._provider_profiles = provider_profiles
        self._custom_orchestrator_factory = orchestrator_factory
        if orchestrator_factory is None:
            self._orchestrator_factory = None
        else:
            self._orchestrator_factory = orchestrator_factory
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    async def submit(
        self,
        batch_id: UUID,
        provider_profile_id: str | None = None,
    ) -> AnalysisJobView:
        batch = await self._repository.get_batch_info(batch_id)
        if batch is None:
            raise LookupError(f"import batch not found: {batch_id}")
        if batch.status not in {"completed", "partial"}:
            raise ValueError(f"import batch is not ready for analysis: {batch.status}")
        sources = await self._repository.select_work_orders(batch_id)
        if not sources:
            raise ValueError("import batch contains no successful work orders")
        profile = (
            await self._provider_profiles.require_validated(provider_profile_id)
            if self._provider_profiles is not None
            else None
        )
        selected_settings = self._settings
        if profile is not None:
            selected_settings = self._settings.model_copy(
                update={
                    "ai_provider_mode": (
                        ProviderMode.LOCAL
                        if profile.deployment_kind == "local"
                        else ProviderMode.REMOTE
                    ),
                    **(
                        {"ai_local_llm_model_id": profile.model_display_name}
                        if profile.deployment_kind == "local"
                        else {"ai_remote_llm_model_id": profile.model_display_name}
                    ),
                    "analysis_pipeline_version": self._ACTIVE_PIPELINE_VERSION,
                    "analysis_schema_version": self._ACTIVE_SCHEMA_VERSION,
                }
            )
        elif self._provider_profiles is not None:
            selected_settings = self._settings.model_copy(
                update={
                    "analysis_pipeline_version": self._ACTIVE_PIPELINE_VERSION,
                    "analysis_schema_version": self._ACTIVE_SCHEMA_VERSION,
                }
            )
        plan = build_provider_plan(selected_settings)
        selected_llm = (
            plan.remote_llm
            if selected_settings.ai_provider_mode is ProviderMode.REMOTE
            else plan.local_llm
        )
        if selected_llm is None:
            raise ValueError("selected LLM provider is not configured")
        idempotency_key = (
            f"analysis:{batch_id}:{self._ACTIVE_PIPELINE_VERSION}:"
            f"{provider_profile_id or selected_llm.provider}:{selected_llm.model_id}"
        )
        selected_settings = selected_settings.model_copy(
            update={
                "analysis_pipeline_version": self._ACTIVE_PIPELINE_VERSION,
                "analysis_schema_version": self._ACTIVE_SCHEMA_VERSION,
            }
        )
        state = await self._repository.create_or_requeue(
            idempotency_key=idempotency_key,
            pipeline_version=self._ACTIVE_PIPELINE_VERSION,
            schema_version=self._ACTIVE_SCHEMA_VERSION,
            model_id=selected_llm.model_id,
            provider=selected_llm.provider,
            model_config_hash=selected_llm.config_hash(),
            total_rows=batch.total_rows,
            target_work_order_count=len(sources),
            batch_id=batch_id,
        )
        freeze_scope = cast(
            Callable[..., Awaitable[object]] | None,
            getattr(self._repository, "freeze_scope", None),
        )
        if callable(freeze_scope):
            await freeze_scope(
                state.job_id,
                batch_id,
                tuple(source.work_order_id for source in sources),
                len(sources),
                self._ACTIVE_PIPELINE_VERSION,
                None,
                (
                    profile.model_dump(mode="json")
                    if profile is not None
                    else {
                        "profile_id": provider_profile_id,
                        "provider": selected_llm.provider,
                        "model_id": selected_llm.model_id,
                        "configuration_hash": selected_llm.config_hash(),
                    }
                ),
                {
                    "understanding_concurrency": self._settings.model_concurrency,
                    "classification_concurrency": self._settings.model_concurrency,
                    "embedding_batch_size": self._settings.model_concurrency,
                    "retrieval_concurrency": self._settings.model_concurrency,
                    "same_event_concurrency": self._settings.model_concurrency,
                },
            )
        view = await self._repository.get_job_view(state.job_id)
        if view is None:
            raise LookupError(f"analysis job not found after creation: {state.job_id}")
        if view.status != "completed":
            self._schedule(state, batch_id, idempotency_key)
        return view

    async def resume_incomplete(self) -> int:
        resumable = await self._repository.list_resumable_jobs()
        for item in resumable:
            self._schedule(
                AnalysisJobState(
                    item.job_id,
                    item.run_id,
                    item.checkpoint_source_row,
                    "queued",
                    item.rows_processed,
                    item.events_extracted,
                    item.embeddings_written,
                ),
                item.batch_id,
                item.idempotency_key,
            )
        return len(resumable)

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

    def _schedule(
        self,
        state: AnalysisJobState,
        batch_id: UUID,
        idempotency_key: str,
    ) -> None:
        if state.job_id in self._tasks:
            return
        self._tasks[state.job_id] = asyncio.create_task(
            self._execute(state, batch_id, idempotency_key)
        )

    async def _execute(
        self,
        state: AnalysisJobState,
        batch_id: UUID,
        idempotency_key: str,
    ) -> None:
        job_id = state.job_id
        run_id = state.run_id
        try:
            await self._repository.mark_running(job_id, run_id, "understanding")
            get_scope = cast(
                Callable[[UUID], Awaitable[FrozenScope | None]] | None,
                getattr(self._repository, "get_scope", None),
            )
            scope = await get_scope(job_id) if callable(get_scope) else None
            profile_id = (
                _profile_id_from_snapshot(scope.provider_profile_snapshot) if scope else None
            )
            orchestrator = await self._create_orchestrator(profile_id)
            execution = await orchestrator.run_import_batch(
                batch_id,
                idempotency_key=idempotency_key,
                analysis_state=state,
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
        except asyncio.CancelledError:
            await self._repository.requeue_interrupted(job_id, run_id, "service_shutdown")
            raise
        except Exception as error:
            await self._repository.fail(job_id, run_id, "analysis_failed", str(error))
        finally:
            self._tasks.pop(job_id, None)

    async def _create_orchestrator(
        self, provider_profile_id: str | None
    ) -> DemoAnalysisOrchestrator:
        if self._custom_orchestrator_factory is not None:
            return await self._custom_orchestrator_factory()
        selected_settings = self._settings
        if self._provider_profiles is not None and provider_profile_id is not None:
            profile = await self._provider_profiles.require_validated(provider_profile_id)
            selected_settings = self._settings.model_copy(
                update={
                    "ai_provider_mode": (
                        ProviderMode.LOCAL
                        if profile.deployment_kind == "local"
                        else ProviderMode.REMOTE
                    ),
                    **(
                        {"ai_local_llm_model_id": profile.model_display_name}
                        if profile.deployment_kind == "local"
                        else {"ai_remote_llm_model_id": profile.model_display_name}
                    ),
                    "analysis_pipeline_version": self._ACTIVE_PIPELINE_VERSION,
                    "analysis_schema_version": self._ACTIVE_SCHEMA_VERSION,
                }
            )
        else:
            selected_settings = self._settings.model_copy(
                update={
                    "analysis_pipeline_version": self._ACTIVE_PIPELINE_VERSION,
                    "analysis_schema_version": self._ACTIVE_SCHEMA_VERSION,
                }
            )
        return await DemoAnalysisOrchestrator.create(selected_settings, self._session_factory)


def _profile_id_from_snapshot(snapshot: dict[str, object] | None) -> str | None:
    if snapshot is None:
        return None
    value = snapshot.get("profile_id")
    return value if isinstance(value, str) else None
