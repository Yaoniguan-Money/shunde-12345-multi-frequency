from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.domain.analysis_jobs import (
    AnalysisBatchInfo,
    AnalysisJobState,
    AnalysisJobView,
    PersistedEvent,
    UnderstandingRecord,
    UnderstandingRepository,
    WorkOrderSource,
)
from backend.app.domain.types import GazetteerSnapshot, VersionTrace
from backend.app.infrastructure.db.models import (
    AnalysisJob,
    AnalysisRun,
    CanonicalEntity,
    ComplaintSegment,
    EntityAliasRuntime,
    EntityMention,
    EventInstance,
    ImportBatch,
    KnowledgeSnapshot,
    WorkOrder,
    WorkOrderEmbedding,
)


class SQLAlchemyUnderstandingRepository(UnderstandingRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def sync_snapshot(self, snapshot: GazetteerSnapshot) -> UUID:
        """Persist deterministic snapshot/entity IDs so resolved mentions can use real FKs."""
        snapshot_id = uuid5(NAMESPACE_URL, f"shunde:gazetteer-snapshot:{snapshot.snapshot_hash}")
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    pg_insert(KnowledgeSnapshot)
                    .values(
                        id=snapshot_id,
                        version=snapshot.version,
                        snapshot_hash=snapshot.snapshot_hash,
                        source_version="shunde_places.sqlite",
                        built_at=snapshot.built_at,
                        entity_count=len(snapshot.entities),
                        metadata_json={"source": "gazetteer_handoff_sqlite"},
                    )
                    .on_conflict_do_nothing()
                )
                for entity in snapshot.entities:
                    entity_id = entity.entity_id
                    await session.execute(
                        pg_insert(CanonicalEntity)
                        .values(
                            id=entity_id,
                            source_namespace="shunde-gazetteer",
                            source_entity_key=str(entity.entity_id),
                            standard_name=entity.standard_name,
                            entity_type=entity.entity_type,
                            administrative_code=None,
                            attributes={"aliases": list(entity.aliases)},
                        )
                        .on_conflict_do_nothing()
                    )
                    for alias in dict.fromkeys((entity.standard_name, *entity.aliases)):
                        await session.execute(
                            pg_insert(EntityAliasRuntime)
                            .values(
                                knowledge_snapshot_id=snapshot_id,
                                canonical_entity_id=entity_id,
                                alias=alias,
                                alias_type="snapshot",
                            )
                            .on_conflict_do_nothing()
                        )
        return snapshot_id

    async def get_batch_info(self, batch_id: UUID) -> AnalysisBatchInfo | None:
        async with self._session_factory() as session:
            batch = await session.get(ImportBatch, batch_id)
            if batch is None:
                return None
            return AnalysisBatchInfo(
                batch_id=batch.id,
                status=batch.status,
                total_rows=batch.total_rows,
                successful_rows=batch.successful_rows,
            )

    async def create_or_requeue(
        self,
        *,
        idempotency_key: str,
        pipeline_version: str,
        schema_version: str,
        model_id: str,
        provider: str,
        model_config_hash: str | None,
        total_rows: int,
        selected_rows: int,
    ) -> AnalysisJobState:
        metrics = {
            "total_rows": total_rows,
            "selected_rows": selected_rows,
            "processed_rows": 0,
            "event_count": 0,
            "match_edge_count": 0,
            "cluster_count": 0,
        }
        async with self._session_factory() as session:
            async with session.begin():
                job = await session.scalar(
                    select(AnalysisJob)
                    .where(
                        AnalysisJob.idempotency_key == idempotency_key,
                        AnalysisJob.pipeline_version == pipeline_version,
                    )
                    .with_for_update()
                )
                if job is None:
                    job = AnalysisJob(
                        idempotency_key=idempotency_key,
                        job_type="demo_analysis",
                        status="queued",
                        pipeline_version=pipeline_version,
                        current_stage="queued",
                        checkpoint_cursor="0",
                        attempts=0,
                        max_attempts=3,
                    )
                    session.add(job)
                    await session.flush()
                    run = AnalysisRun(
                        analysis_job_id=job.id,
                        run_number=1,
                        status="queued",
                        provider=provider,
                        model_id=model_id,
                        model_config_hash=model_config_hash,
                        schema_version=schema_version,
                        pipeline_version=pipeline_version,
                        metrics=metrics,
                    )
                    session.add(run)
                    await session.flush()
                    return AnalysisJobState(job.id, run.id, 0, job.status)
                run = await session.scalar(
                    select(AnalysisRun)
                    .where(AnalysisRun.analysis_job_id == job.id)
                    .order_by(AnalysisRun.run_number.desc())
                    .with_for_update()
                )
                if run is None:
                    run = AnalysisRun(
                        analysis_job_id=job.id,
                        run_number=1,
                        status="queued",
                        provider=provider,
                        model_id=model_id,
                        model_config_hash=model_config_hash,
                        schema_version=schema_version,
                        pipeline_version=pipeline_version,
                        metrics=metrics,
                    )
                    session.add(run)
                    await session.flush()
                elif job.status == "failed":
                    job.status = "queued"
                    job.current_stage = "queued"
                    job.error_code = None
                    job.error_metadata = None
                    run.status = "queued"
                    run.metrics = {**(run.metrics or {}), **metrics}
                return AnalysisJobState(
                    job.id,
                    run.id,
                    self._checkpoint(job.checkpoint_cursor),
                    job.status,
                )

    async def get_job_view(self, job_id: UUID) -> AnalysisJobView | None:
        async with self._session_factory() as session:
            job = await session.get(AnalysisJob, job_id)
            if job is None:
                return None
            run = await session.scalar(
                select(AnalysisRun)
                .where(AnalysisRun.analysis_job_id == job.id)
                .order_by(AnalysisRun.run_number.desc())
            )
            if run is None:
                return AnalysisJobView(
                    job_id=job.id,
                    status=job.status,
                    total_rows=0,
                    selected_rows=0,
                    processed_rows=0,
                    event_count=0,
                    match_edge_count=0,
                    cluster_count=0,
                    started_at=None,
                    finished_at=None,
                    error=self._error_message(job.error_metadata),
                    trace=None,
                )
            metrics = run.metrics or {}
            return AnalysisJobView(
                job_id=job.id,
                status=job.status,
                total_rows=self._metric_int(metrics, "total_rows"),
                selected_rows=self._metric_int(metrics, "selected_rows"),
                processed_rows=self._metric_int(metrics, "processed_rows", "rows_processed"),
                event_count=self._metric_int(metrics, "event_count", "events_extracted"),
                match_edge_count=self._metric_int(metrics, "match_edge_count"),
                cluster_count=self._metric_int(metrics, "cluster_count"),
                started_at=run.created_at,
                finished_at=run.completed_at,
                error=self._error_message(job.error_metadata),
                trace=VersionTrace(
                    model_id=run.model_id,
                    model_config_hash=run.model_config_hash,
                    schema_version=run.schema_version,
                    knowledge_snapshot_id=run.knowledge_snapshot_id,
                    pipeline_version=run.pipeline_version,
                    provider=run.provider,
                ),
            )

    async def start_or_resume(
        self,
        *,
        idempotency_key: str,
        pipeline_version: str,
        schema_version: str,
        model_id: str,
        provider: str,
        model_config_hash: str | None = None,
        total_rows: int,
    ) -> AnalysisJobState:
        async with self._session_factory() as session:
            async with session.begin():
                job = await session.scalar(
                    select(AnalysisJob).where(
                        AnalysisJob.idempotency_key == idempotency_key,
                        AnalysisJob.pipeline_version == pipeline_version,
                    )
                )
                if job is None:
                    job = AnalysisJob(
                        idempotency_key=idempotency_key,
                        job_type="understanding_and_embedding",
                        status="running",
                        pipeline_version=pipeline_version,
                        current_stage="segment",
                        checkpoint_cursor="0",
                        attempts=1,
                        max_attempts=3,
                    )
                    session.add(job)
                    await session.flush()
                    run = AnalysisRun(
                        analysis_job_id=job.id,
                        run_number=1,
                        status="running",
                        provider=provider,
                        model_id=model_id,
                        model_config_hash=model_config_hash,
                        schema_version=schema_version,
                        pipeline_version=pipeline_version,
                        metrics={"total_rows": total_rows},
                    )
                    session.add(run)
                    await session.flush()
                    return AnalysisJobState(job.id, run.id, 0, job.status)
                run = await session.scalar(
                    select(AnalysisRun)
                    .where(AnalysisRun.analysis_job_id == job.id)
                    .order_by(AnalysisRun.run_number.desc())
                )
                if run is None:
                    run = AnalysisRun(
                        analysis_job_id=job.id,
                        run_number=1,
                        status="running",
                        provider=provider,
                        model_id=model_id,
                        model_config_hash=model_config_hash,
                        schema_version=schema_version,
                        pipeline_version=pipeline_version,
                        metrics={"total_rows": total_rows},
                    )
                    session.add(run)
                    await session.flush()
                checkpoint = self._checkpoint(job.checkpoint_cursor)
                if job.status != "completed":
                    job.status = "running"
                    job.current_stage = "segment"
                    run.status = "running"
                return AnalysisJobState(job.id, run.id, checkpoint, job.status)

    async def load_work_orders(
        self,
        batch_id: UUID,
        after_source_row: int,
        limit: int,
        max_source_row: int | None = None,
    ) -> tuple[WorkOrderSource, ...]:
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(WorkOrder)
                    .where(
                        WorkOrder.import_batch_id == batch_id,
                        WorkOrder.source_row_number > after_source_row,
                        *(
                            (WorkOrder.source_row_number <= max_source_row,)
                            if max_source_row is not None
                            else ()
                        ),
                    )
                    .order_by(WorkOrder.source_row_number)
                    .limit(limit)
                )
            ).all()
            return tuple(
                WorkOrderSource(row.id, row.source_row_number, row.raw_title, row.raw_content)
                for row in rows
            )

    async def persist_records(
        self,
        run_id: UUID,
        records: tuple[UnderstandingRecord, ...],
        pipeline_version: str,
        schema_version: str,
    ) -> tuple[PersistedEvent, ...]:
        persisted: list[PersistedEvent] = []
        async with self._session_factory() as session:
            async with session.begin():
                run = await session.get(AnalysisRun, run_id)
                if run is None:
                    raise LookupError(f"analysis run not found: {run_id}")
                for record in records:
                    for segment in record.segments:
                        await session.execute(
                            pg_insert(ComplaintSegment)
                            .values(
                                work_order_id=record.work_order_id,
                                segment_type=segment.segment_type.value,
                                text=segment.text,
                                ordinal=segment.ordinal,
                                start_offset=segment.start_offset,
                                end_offset=segment.end_offset,
                            )
                            .on_conflict_do_nothing(
                                index_elements=[
                                    ComplaintSegment.work_order_id,
                                    ComplaintSegment.ordinal,
                                ]
                            )
                        )
                    trace = record.trace
                    mention_ids = tuple(
                        mention.canonical_entity_id
                        for mention in record.understanding.mentions
                        if mention.canonical_entity_id is not None
                    )
                    canonical_ids = set(
                        (
                            await session.scalars(
                                select(CanonicalEntity.id).where(
                                    CanonicalEntity.id.in_(mention_ids)
                                )
                            )
                        ).all()
                    )
                    for ordinal, event in enumerate(record.understanding.events):
                        event_id = uuid4()
                        event_values = {
                            "id": event_id,
                            "work_order_id": record.work_order_id,
                            "ordinal": ordinal,
                            "event_type": event.event_type,
                            "behavior": event.behavior,
                            "normalized_summary": event.normalized_summary,
                            "entity_ids": [
                                str(record.understanding.mentions[index].canonical_entity_id)
                                for index in event.mention_indexes
                                if 0 <= index < len(record.understanding.mentions)
                                and record.understanding.mentions[index].canonical_entity_id
                            ],
                            "location_signals": event.location_signals,
                            "time_signals": list(event.time_signals),
                            "evidence": {
                                "source": "raw_segment_quote",
                                "items": [
                                    {
                                        "segment_ordinal": item.segment_ordinal,
                                        "segment_type": item.segment_type,
                                        "quote": item.quote,
                                        "start_offset": item.start_offset,
                                        "end_offset": item.end_offset,
                                        "validation": "exact_quote",
                                    }
                                    for item in event.evidence
                                ],
                                "mention_indexes": event.mention_indexes,
                                "analysis_run_id": str(run_id),
                            },
                            "model_id": trace.model_id,
                            "provider": trace.provider,
                            "model_config_hash": trace.model_config_hash,
                            "schema_version": schema_version,
                            "knowledge_snapshot_id": trace.knowledge_snapshot_id,
                            "pipeline_version": pipeline_version,
                        }
                        await session.execute(
                            pg_insert(EventInstance)
                            .values(**event_values)
                            .on_conflict_do_nothing(
                                index_elements=[
                                    EventInstance.work_order_id,
                                    EventInstance.ordinal,
                                    EventInstance.pipeline_version,
                                ]
                            )
                        )
                        existing_id = await session.scalar(
                            select(EventInstance.id).where(
                                EventInstance.work_order_id == record.work_order_id,
                                EventInstance.ordinal == ordinal,
                                EventInstance.pipeline_version == pipeline_version,
                            )
                        )
                        if existing_id is not None:
                            persisted.append(
                                PersistedEvent(
                                    record.work_order_id,
                                    existing_id,
                                    event.normalized_summary,
                                )
                            )
                    for ordinal, mention in enumerate(record.understanding.mentions):
                        await session.execute(
                            pg_insert(EntityMention)
                            .values(
                                work_order_id=record.work_order_id,
                                complaint_segment_id=None,
                                mention_text=mention.text,
                                mention_type=mention.mention_type,
                                ordinal=ordinal,
                                start_offset=mention.start_offset,
                                end_offset=mention.end_offset,
                                canonical_entity_id=(
                                    mention.canonical_entity_id
                                    if mention.canonical_entity_id in canonical_ids
                                    else None
                                ),
                                resolution_state=mention.resolution_state,
                                confidence=mention.confidence,
                                evidence={
                                    "evidence": mention.evidence,
                                    "candidate_entity_id": str(mention.canonical_entity_id)
                                    if mention.canonical_entity_id
                                    else None,
                                },
                                model_id=trace.model_id,
                                provider=trace.provider,
                                model_config_hash=trace.model_config_hash,
                                schema_version=schema_version,
                                knowledge_snapshot_id=trace.knowledge_snapshot_id,
                                pipeline_version=pipeline_version,
                            )
                            .on_conflict_do_nothing(
                                index_elements=[
                                    EntityMention.work_order_id,
                                    EntityMention.ordinal,
                                    EntityMention.pipeline_version,
                                ]
                            )
                        )
                previous = (run.metrics or {}).get("records_persisted", 0)
                prior_count = previous if isinstance(previous, int) else 0
                run.metrics = {
                    **(run.metrics or {}),
                    "records_persisted": prior_count + len(records),
                }
        return tuple(persisted)

    async def persist_embeddings(
        self,
        run_id: UUID,
        embeddings: tuple[
            tuple[UUID, UUID | None, str, tuple[float, ...], str, VersionTrace | None], ...
        ],
        pipeline_version: str,
        schema_version: str,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                run = await session.get(AnalysisRun, run_id)
                if run is None:
                    raise LookupError(f"analysis run not found: {run_id}")
                for (
                    work_order_id,
                    event_id,
                    content_hash,
                    vector,
                    model_id,
                    embedding_trace,
                ) in embeddings:
                    await session.execute(
                        pg_insert(WorkOrderEmbedding)
                        .values(
                            work_order_id=work_order_id,
                            event_instance_id=event_id,
                            content_hash=content_hash,
                            dimensions=len(vector),
                            embedding=list(vector),
                            model_id=model_id,
                            provider=(embedding_trace.provider if embedding_trace else None),
                            model_config_hash=(
                                embedding_trace.model_config_hash if embedding_trace else None
                            ),
                            schema_version=schema_version,
                            knowledge_snapshot_id=(
                                embedding_trace.knowledge_snapshot_id if embedding_trace else None
                            ),
                            pipeline_version=pipeline_version,
                        )
                        .on_conflict_do_nothing(
                            index_elements=[
                                WorkOrderEmbedding.work_order_id,
                                WorkOrderEmbedding.content_hash,
                                WorkOrderEmbedding.model_id,
                            ]
                        )
                    )
                previous = (run.metrics or {}).get("embeddings_persisted", 0)
                prior_count = previous if isinstance(previous, int) else 0
                run.metrics = {
                    **(run.metrics or {}),
                    "embeddings_persisted": prior_count + len(embeddings),
                }

    async def checkpoint(
        self, job_id: UUID, run_id: UUID, source_row: int, metrics: dict[str, object]
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                job = await session.get(AnalysisJob, job_id)
                run = await session.get(AnalysisRun, run_id)
                if job is None or run is None:
                    raise LookupError("analysis job or run not found")
                job.checkpoint_cursor = str(source_row)
                job.current_stage = "embed"
                run.metrics = {**(run.metrics or {}), **metrics}

    async def finish(self, job_id: UUID, run_id: UUID, metrics: dict[str, object]) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                job = await session.get(AnalysisJob, job_id)
                run = await session.get(AnalysisRun, run_id)
                if job is None or run is None:
                    raise LookupError("analysis job or run not found")
                job.status = "completed"
                job.current_stage = "completed"
                run.status = "completed"
                run.completed_at = datetime.now(UTC)
                run.metrics = {**(run.metrics or {}), **metrics}

    async def fail(self, job_id: UUID, run_id: UUID, code: str, message: str) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                job = await session.get(AnalysisJob, job_id)
                run = await session.get(AnalysisRun, run_id)
                if job is None or run is None:
                    raise LookupError("analysis job or run not found")
                job.status = "failed"
                job.error_code = code
                job.error_metadata = {"message": message}
                run.status = "failed"

    @staticmethod
    def _checkpoint(value: str | None) -> int:
        try:
            return max(0, int(value or "0"))
        except ValueError:
            return 0

    @staticmethod
    def _metric_int(metrics: dict[str, object], *keys: str) -> int:
        for key in keys:
            value = metrics.get(key)
            if isinstance(value, int):
                return value
        return 0

    @staticmethod
    def _error_message(metadata: dict[str, object] | None) -> str | None:
        if metadata is None:
            return None
        value = metadata.get("message")
        return value if isinstance(value, str) else None
