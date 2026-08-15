"""SQLAlchemy repositories for event matching and demo graph persistence."""

import hashlib
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.domain.ports.repositories import EventGraphRepository, EventRepository
from backend.app.domain.types import (
    EntityId,
    EventClusterId,
    EventClusterRecord,
    EventForMatching,
    EventInstanceId,
    EventInstanceRecord,
    EventMatchEdgeRecord,
    JobId,
    SameEventEvidence,
    VersionTrace,
    WorkOrderId,
)
from backend.app.infrastructure.db.models import (
    AnalysisJob,
    AnalysisRun,
    EventCluster,
    EventClusterMember,
    EventInstance,
    EventMatchEdge,
    WorkOrder,
)


class SQLAlchemyEventRepository(EventRepository, EventGraphRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_instance(self, event_id: EventInstanceId) -> EventInstanceRecord | None:
        async with self._session_factory() as session:
            event = await session.get(EventInstance, event_id)
            if event is None:
                return None
            return EventInstanceRecord(
                event_id=EventInstanceId(event.id),
                work_order_id=WorkOrderId(event.work_order_id),
                ordinal=event.ordinal,
                event_type=event.event_type,
                normalized_summary=event.normalized_summary,
            )

    async def get_cluster(self, cluster_id: EventClusterId) -> EventClusterRecord | None:
        async with self._session_factory() as session:
            cluster = await session.get(EventCluster, cluster_id)
            if cluster is None:
                return None
            member_ids = (
                await session.scalars(
                    select(EventClusterMember.event_instance_id).where(
                        EventClusterMember.event_cluster_id == cluster.id
                    )
                )
            ).all()
            return EventClusterRecord(
                cluster_id=EventClusterId(cluster.id),
                name=cluster.name,
                member_ids=tuple(EventInstanceId(value) for value in member_ids),
            )

    async def get_for_matching(self, event_id: EventInstanceId) -> EventForMatching | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(EventInstance, WorkOrder)
                    .join(WorkOrder, WorkOrder.id == EventInstance.work_order_id)
                    .where(EventInstance.id == event_id)
                )
            ).first()
            if row is None:
                return None
            event, work_order = row
            raw_entity_ids = cast(list[object], event.entity_ids or [])
            entity_ids = tuple(
                EntityId(UUID(str(value))) for value in raw_entity_ids if _is_uuid(value)
            )
            event_json = cast(dict[str, object], event.evidence or {})
            raw_evidence = event_json.get("items", [])
            raw_evidence_items: list[object] = (
                list(cast(list[object], raw_evidence)) if isinstance(raw_evidence, list) else []
            )
            evidence = tuple(
                cast(dict[str, object], item)
                for item in raw_evidence_items
                if isinstance(item, dict)
            )
            raw_locations = cast(list[object], event.location_signals or [])
            raw_times = cast(list[object], event.time_signals or [])
            return EventForMatching(
                event_id=EventInstanceId(event.id),
                work_order_id=work_order.id,
                event_type=event.event_type,
                behavior=event.behavior,
                normalized_summary=event.normalized_summary,
                entity_ids=entity_ids,
                location_signals=tuple(str(value) for value in raw_locations),
                time_signals=tuple(str(value) for value in raw_times),
                evidence=evidence,
                raw_title=work_order.raw_title,
                raw_content=work_order.raw_content,
            )

    async def list_event_ids(
        self, work_order_ids: tuple[WorkOrderId, ...], pipeline_version: str
    ) -> tuple[EventInstanceId, ...]:
        if not work_order_ids:
            return ()
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(EventInstance.id)
                    .where(
                        EventInstance.work_order_id.in_(work_order_ids),
                        EventInstance.pipeline_version == pipeline_version,
                    )
                    .order_by(EventInstance.work_order_id, EventInstance.ordinal)
                )
            ).all()
            return tuple(EventInstanceId(value) for value in rows)

    async def start_run(self, *, pipeline_version: str, schema_version: str) -> tuple[JobId, UUID]:
        async with self._session_factory() as session:
            async with session.begin():
                job = AnalysisJob(
                    idempotency_key=f"demo-graph:{pipeline_version}:{uuid4()}",
                    job_type="event_graph",
                    status="running",
                    pipeline_version=pipeline_version,
                    current_stage="matching",
                    checkpoint_cursor="0",
                    attempts=1,
                    max_attempts=1,
                )
                session.add(job)
                await session.flush()
                run = AnalysisRun(
                    analysis_job_id=job.id,
                    run_number=1,
                    status="running",
                    schema_version=schema_version,
                    pipeline_version=pipeline_version,
                    metrics={},
                )
                session.add(run)
                await session.flush()
                return JobId(job.id), run.id

    async def save_match_edge(
        self,
        run_id: UUID,
        edge: EventMatchEdgeRecord,
        *,
        pipeline_version: str,
        schema_version: str,
    ) -> None:
        left_id, right_id = sorted(
            (edge.left_event_id, edge.right_event_id), key=lambda value: str(value)
        )
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    pg_insert(EventMatchEdge)
                    .values(
                        left_event_id=left_id,
                        right_event_id=right_id,
                        analysis_run_id=run_id,
                        same_event=edge.same_event,
                        confidence=edge.confidence,
                        evidence=_same_event_evidence_dict(edge.evidence),
                        provider=edge.trace.provider,
                        model_id=edge.trace.model_id,
                        model_config_hash=edge.trace.model_config_hash,
                        schema_version=schema_version,
                        knowledge_snapshot_id=edge.trace.knowledge_snapshot_id,
                        pipeline_version=pipeline_version,
                    )
                    .on_conflict_do_nothing(
                        index_elements=[
                            EventMatchEdge.left_event_id,
                            EventMatchEdge.right_event_id,
                            EventMatchEdge.analysis_run_id,
                        ]
                    )
                )

    async def list_positive_edges(self, run_id: UUID) -> tuple[EventMatchEdgeRecord, ...]:
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(EventMatchEdge)
                    .where(
                        EventMatchEdge.analysis_run_id == run_id,
                        EventMatchEdge.same_event.is_(True),
                    )
                    .order_by(EventMatchEdge.confidence.desc())
                )
            ).all()
            return tuple(_edge_record(row) for row in rows)

    async def save_cluster(
        self,
        run_id: UUID,
        member_ids: tuple[EventInstanceId, ...],
        *,
        name: str,
        confidence: float,
        evidence: dict[str, object],
        trace: VersionTrace,
        pipeline_version: str,
        schema_version: str,
    ) -> EventClusterId:
        cluster_id = EventClusterId(uuid4())
        async with self._session_factory() as session:
            async with session.begin():
                unique_member_ids = tuple(dict.fromkeys(member_ids))
                member_rows = (
                    await session.execute(
                        select(EventInstance.id, EventInstance.work_order_id).where(
                            EventInstance.id.in_(unique_member_ids)
                        )
                    )
                ).all()
                if len(member_rows) != len(unique_member_ids):
                    raise LookupError("every cluster member event must exist")
                if len({row.work_order_id for row in member_rows}) < 2:
                    raise ValueError(
                        "multi-frequency cluster requires at least two distinct work orders"
                    )
                signature = _member_signature(unique_member_ids)
                existing = await session.scalar(
                    select(EventCluster.id).where(EventCluster.member_signature == signature)
                )
                if existing is None:
                    existing = await _find_legacy_cluster(session, unique_member_ids)
                if existing is not None:
                    return EventClusterId(existing)
                session.add(
                    EventCluster(
                        id=cluster_id,
                        name=name,
                        status="active",
                        confidence=confidence,
                        evidence=evidence,
                        handling_status="unhandled",
                        review_status="pending_review",
                        member_signature=signature,
                        provider=trace.provider,
                        model_id=trace.model_id,
                        model_config_hash=trace.model_config_hash,
                        schema_version=schema_version,
                        knowledge_snapshot_id=trace.knowledge_snapshot_id,
                        pipeline_version=pipeline_version,
                    )
                )
                for event_id in unique_member_ids:
                    session.add(
                        EventClusterMember(
                            event_cluster_id=cluster_id,
                            event_instance_id=event_id,
                            analysis_run_id=run_id,
                            membership_confidence=confidence,
                        )
                    )
        return cluster_id

    async def finish_run(self, run_id: UUID, metrics: dict[str, object]) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                run = await session.get(AnalysisRun, run_id)
                if run is None:
                    raise LookupError(f"analysis run not found: {run_id}")
                run.status = "completed"
                run.completed_at = datetime.now(UTC)
                run.metrics = {**(run.metrics or {}), **metrics}


def _is_uuid(value: object) -> bool:
    try:
        UUID(str(value))
        return True
    except ValueError:
        return False


def _member_signature(member_ids: tuple[EventInstanceId, ...]) -> str:
    payload = "\n".join(sorted(str(value) for value in member_ids))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


async def _find_legacy_cluster(
    session: AsyncSession, member_ids: tuple[EventInstanceId, ...]
) -> UUID | None:
    expected = set(member_ids)
    candidates = (
        await session.scalars(
            select(EventClusterMember.event_cluster_id).where(
                EventClusterMember.event_instance_id == member_ids[0]
            )
        )
    ).all()
    for candidate in candidates:
        actual = set(
            (
                await session.scalars(
                    select(EventClusterMember.event_instance_id).where(
                        EventClusterMember.event_cluster_id == candidate
                    )
                )
            ).all()
        )
        if actual == expected:
            cluster = await session.get(EventCluster, candidate)
            if cluster is not None and cluster.member_signature is None:
                cluster.member_signature = _member_signature(member_ids)
            return candidate
    return None


def _same_event_evidence_dict(evidence: SameEventEvidence) -> dict[str, object]:
    return {
        "same_entity": evidence.same_entity,
        "same_location": evidence.same_location,
        "same_issue": evidence.same_issue,
        "time_compatible": evidence.time_compatible,
        "contradictions": list(evidence.contradictions),
    }


def _edge_record(row: EventMatchEdge) -> EventMatchEdgeRecord:
    raw: dict[str, object] = row.evidence or {}
    return EventMatchEdgeRecord(
        left_event_id=EventInstanceId(row.left_event_id),
        right_event_id=EventInstanceId(row.right_event_id),
        same_event=row.same_event,
        confidence=row.confidence,
        evidence=SameEventEvidence(
            same_entity=_optional_bool(raw.get("same_entity")),
            same_location=_optional_bool(raw.get("same_location")),
            same_issue=_optional_bool(raw.get("same_issue")),
            time_compatible=_optional_bool(raw.get("time_compatible")),
            contradictions=_string_tuple(raw.get("contradictions")),
        ),
        trace=VersionTrace(
            model_id=row.model_id,
            model_config_hash=row.model_config_hash,
            schema_version=row.schema_version,
            knowledge_snapshot_id=row.knowledge_snapshot_id,
            pipeline_version=row.pipeline_version,
            provider=row.provider,
        ),
    )


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _string_tuple(value: object) -> tuple[str, ...]:
    values = cast(list[object], value) if isinstance(value, list) else []
    return tuple(str(item) for item in values)
