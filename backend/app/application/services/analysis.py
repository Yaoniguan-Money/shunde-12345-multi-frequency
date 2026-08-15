"""Shared bounded analysis orchestration for HTTP jobs and the Demo Core script."""

import hashlib
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.application.services.event_graph import EventGraphRunResult, EventGraphService
from backend.app.application.services.indexing import UnderstandingAndIndexingPipeline
from backend.app.application.services.understanding import WorkOrderUnderstandingService
from backend.app.config import Settings
from backend.app.domain.analysis_jobs import UnderstandingRecord, WorkOrderSource
from backend.app.domain.services.segmentation import RuleBasedWorkOrderSegmenter
from backend.app.domain.types import (
    EmbeddingRequest,
    EventInstanceId,
    EventMatchEdgeRecord,
    ProviderMode,
    WorkOrderId,
)
from backend.app.infrastructure.ai.factory import AIProviderBundle, build_provider_bundle
from backend.app.infrastructure.ai.same_event import RemoteSameEventMatcher
from backend.app.infrastructure.db.analysis import SQLAlchemyUnderstandingRepository
from backend.app.infrastructure.db.events import SQLAlchemyEventRepository
from backend.app.infrastructure.db.retrieval import PostgresCandidateRetriever
from backend.app.infrastructure.knowledge.gazetteer import GazetteerHttpAdapter
from backend.app.infrastructure.knowledge.resolver import RuntimeEntityResolver
from backend.app.infrastructure.knowledge.snapshot import (
    GazetteerSnapshotBuilder,
    RuntimeSnapshotStore,
)

DEMO_MAX_WORK_ORDERS = 300


@dataclass(frozen=True, slots=True)
class AnalysisExecution:
    job_id: UUID
    run_id: UUID
    work_order_ids: tuple[UUID, ...]
    event_ids: tuple[EventInstanceId, ...]
    decisions: tuple[EventMatchEdgeRecord, ...]
    cluster_ids: tuple[UUID, ...]
    processed_rows: int
    embeddings_written: int
    embedding_dimensions: int

    @property
    def event_count(self) -> int:
        return len(self.event_ids)

    @property
    def match_edge_count(self) -> int:
        return len(self.decisions)

    @property
    def cluster_count(self) -> int:
        return len(self.cluster_ids)


class DemoAnalysisOrchestrator:
    """One application seam for understanding, indexing, matching and clustering."""

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        providers: AIProviderBundle,
        understanding_repository: SQLAlchemyUnderstandingRepository,
        event_repository: SQLAlchemyEventRepository,
        gazetteer: RuntimeEntityResolver,
        snapshot_id: UUID,
        provider_health: dict[str, dict[str, str]],
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._providers = providers
        self._understanding_repository = understanding_repository
        self._event_repository = event_repository
        self._gazetteer = gazetteer
        self._snapshot_id = snapshot_id
        self.provider_health = provider_health

    @classmethod
    async def create(
        cls,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> "DemoAnalysisOrchestrator":
        if settings.ai_provider_mode is not ProviderMode.REMOTE:
            raise RuntimeError(
                "analysis jobs require explicit SHUNDE_AI_PROVIDER_MODE=remote; no local fallback"
            )
        providers = build_provider_bundle(settings)
        if providers.plan.remote_llm is None or providers.plan.remote_embedding is None:
            raise RuntimeError("remote LLM and embedding endpoints must both be configured")
        provider_health = await providers.health()
        understanding_repository = SQLAlchemyUnderstandingRepository(session_factory)
        gazetteer, snapshot_id = await _build_gazetteer(settings, understanding_repository)
        return cls(
            settings,
            session_factory,
            providers,
            understanding_repository,
            SQLAlchemyEventRepository(session_factory),
            gazetteer,
            snapshot_id,
            provider_health,
        )

    @property
    def event_repository(self) -> SQLAlchemyEventRepository:
        return self._event_repository

    @property
    def providers(self) -> AIProviderBundle:
        return self._providers

    async def run_import_batch(
        self,
        batch_id: UUID,
        max_work_orders: int,
        *,
        idempotency_key: str,
        candidate_limit: int = 10,
        selection_mode: str = "sequential",
    ) -> AnalysisExecution:
        _validate_max_work_orders(max_work_orders)
        batch = await self._understanding_repository.get_batch_info(batch_id)
        if batch is None:
            raise LookupError(f"import batch not found: {batch_id}")
        if batch.status not in {"completed", "partial"}:
            raise ValueError(f"import batch is not ready for analysis: {batch.status}")
        sources = await self._understanding_repository.select_work_orders(
            batch_id, max_work_orders, selection_mode
        )
        if not sources:
            raise ValueError("import batch contains no successful work orders")
        pipeline = self._build_indexing_pipeline()
        indexing = await pipeline.run(
            batch_id,
            batch.total_rows,
            max_rows=len(sources),
            selected_work_order_ids=tuple(source.work_order_id for source in sources),
            idempotency_key=idempotency_key,
        )
        event_ids = await self._event_repository.list_event_ids(
            tuple(WorkOrderId(source.work_order_id) for source in sources),
            self._settings.analysis_pipeline_version,
        )
        graph = await self._run_graph(event_ids, candidate_limit=candidate_limit)
        return AnalysisExecution(
            job_id=indexing.job_id,
            run_id=indexing.run_id,
            work_order_ids=tuple(source.work_order_id for source in sources),
            event_ids=event_ids,
            decisions=graph.decisions,
            cluster_ids=graph.cluster_ids,
            processed_rows=indexing.rows_processed or len(sources),
            embeddings_written=indexing.embeddings_written,
            embedding_dimensions=0,
        )

    async def run_selected(
        self,
        sources: tuple[WorkOrderSource, ...],
        *,
        candidate_limit: int = 10,
    ) -> AnalysisExecution:
        """Run the same AI/graph seam for the script's query-selected Demo rows."""
        if not sources:
            raise ValueError("at least one work order is required")
        graph_job_id, understanding_run_id = await self._event_repository.start_run(
            pipeline_version="demo-understanding.v2",
            schema_version=self._settings.analysis_schema_version,
        )
        understanding = self._build_understanding()
        results = await understanding.understand_batch(
            tuple(
                (source.work_order_id, source.raw_title, source.raw_content) for source in sources
            )
        )
        records = tuple(
            UnderstandingRecord(
                result.work_order_id,
                result.segments,
                result.understanding,
                result.trace,
            )
            for result in results
        )
        persisted_events = await self._understanding_repository.persist_records(
            understanding_run_id,
            records,
            self._settings.analysis_pipeline_version,
            self._settings.analysis_schema_version,
        )
        embedding_requests = tuple(
            EmbeddingRequest(
                str(event.event_id),
                event.text,
                schema_version=self._settings.analysis_schema_version,
                pipeline_version="demo-embedding.v1",
            )
            for event in persisted_events
        )
        embedding_results = await self._providers.embeddings.embed_batch(embedding_requests)
        await self._understanding_repository.persist_embeddings(
            understanding_run_id,
            tuple(
                (
                    event.work_order_id,
                    event.event_id,
                    hashlib.sha256(event.text.encode("utf-8")).hexdigest(),
                    embedding.vector,
                    embedding.model_id,
                    embedding.trace,
                )
                for event, embedding in zip(persisted_events, embedding_results, strict=True)
            ),
            "demo-embedding.v1",
            self._settings.analysis_schema_version,
        )
        await self._event_repository.finish_run(
            understanding_run_id,
            {
                "work_orders": len(sources),
                "events": len(persisted_events),
                "embeddings": len(embedding_results),
            },
        )
        event_ids = tuple(EventInstanceId(event.event_id) for event in persisted_events)
        graph = await self._run_graph(event_ids, candidate_limit=candidate_limit)
        return AnalysisExecution(
            job_id=graph_job_id,
            run_id=understanding_run_id,
            work_order_ids=tuple(source.work_order_id for source in sources),
            event_ids=event_ids,
            decisions=graph.decisions,
            cluster_ids=graph.cluster_ids,
            processed_rows=len(sources),
            embeddings_written=len(embedding_results),
            embedding_dimensions=len(embedding_results[0].vector) if embedding_results else 0,
        )

    def _build_understanding(self) -> WorkOrderUnderstandingService:
        return WorkOrderUnderstandingService(
            RuleBasedWorkOrderSegmenter(),
            self._providers.llm,
            gazetteer=self._gazetteer,
            pipeline_version=self._settings.analysis_pipeline_version,
            schema_version=self._settings.analysis_schema_version,
            knowledge_snapshot_id=self._snapshot_id,
        )

    def _build_indexing_pipeline(self) -> UnderstandingAndIndexingPipeline:
        remote_llm = self._providers.plan.remote_llm
        remote_embedding = self._providers.plan.remote_embedding
        if remote_llm is None or remote_embedding is None:
            raise RuntimeError("remote provider plan is incomplete")
        return UnderstandingAndIndexingPipeline(
            self._understanding_repository,
            self._build_understanding(),
            self._providers.embeddings,
            pipeline_version=self._settings.analysis_pipeline_version,
            schema_version=self._settings.analysis_schema_version,
            model_id=remote_llm.model_id,
            embedding_model_id=remote_embedding.model_id,
            provider=remote_llm.provider,
            model_config_hash=remote_llm.config_hash(),
            chunk_size=4,
        )

    async def _run_graph(
        self, event_ids: tuple[EventInstanceId, ...], *, candidate_limit: int
    ) -> EventGraphRunResult:
        if candidate_limit < 1:
            raise ValueError("candidate_limit must be positive")
        if not event_ids:
            return EventGraphRunResult(UUID(int=0), (), ())
        remote_embedding = self._providers.plan.remote_embedding
        if remote_embedding is None:
            raise RuntimeError("remote embedding provider is not configured")
        matcher = RemoteSameEventMatcher(
            self._event_repository,
            self._providers.llm,
            pipeline_version="demo-same-event.v1",
            schema_version="same-event.v1",
        )
        graph = EventGraphService(
            self._event_repository,
            self._event_repository,
            PostgresCandidateRetriever(
                self._session_factory,
                self._providers.embeddings,
                model_id=remote_embedding.model_id,
            ),
            matcher,
        )
        return await graph.run(event_ids, candidate_limit=candidate_limit)


async def _build_gazetteer(
    settings: Settings,
    repository: SQLAlchemyUnderstandingRepository,
) -> tuple[RuntimeEntityResolver, UUID]:
    if settings.gazetteer_home is None and settings.gazetteer_database_path is None:
        raise RuntimeError("SHUNDE_GAZETTEER_HOME or SHUNDE_GAZETTEER_DATABASE_PATH is required")
    database_path = settings.gazetteer_database_path or (
        settings.gazetteer_home / "地名服务" / "shunde_places.db"
        if settings.gazetteer_home is not None
        else None
    )
    if database_path is None:
        raise RuntimeError("gazetteer path configuration is incomplete")
    snapshot = GazetteerSnapshotBuilder(database_path).build()
    RuntimeSnapshotStore(settings.gazetteer_snapshot_path).save(snapshot)
    snapshot_id = await repository.sync_snapshot(snapshot)
    remote = GazetteerHttpAdapter(
        str(settings.gazetteer_api_base_url), settings.dependency_timeout_seconds
    )
    health = await remote.health()
    if not health.available:
        raise RuntimeError("gazetteer live service is unavailable")
    return RuntimeEntityResolver(snapshot, remote), snapshot_id


def _validate_max_work_orders(value: int) -> None:
    if value < 1 or value > DEMO_MAX_WORK_ORDERS:
        raise ValueError(f"max_work_orders must be between 1 and {DEMO_MAX_WORK_ORDERS}")
