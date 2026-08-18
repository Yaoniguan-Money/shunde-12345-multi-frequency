"""SQLAlchemy adapter for Agent retrieval, worksets and audited batch operations.

This module only reads V2 work-order/event/cluster projections.  It never writes
to the V2 understanding, same-event, or clustering tables.
"""

import csv
import io
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import TypedDict, cast
from uuid import UUID

from sqlalchemy import Text, or_, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from backend.app.infrastructure.db.models import (
    AgentActionPreview,
    AuditLog,
    EventCluster,
    EventClusterMember,
    EventInstance,
    WorkOrder,
    WorkOrderEmbedding,
    WorkOrderHandlingRecord,
    Workset,
    WorksetCluster,
    WorksetWorkOrder,
)


class AgentRecord(TypedDict):
    work_order_id: UUID
    external_work_order_number: str | None
    title: str | None
    created_at: datetime
    normalized_summary: str | None
    location: str | None
    event_type: str | None
    handling_status: str
    cluster_ids: list[UUID]
    is_multi_frequency: bool
    retrieval_evidence: list[str]
    rank: int


class AgentActionSnapshot(TypedDict):
    work_order_ids: list[str]
    cluster_ids: list[str]
    before_status_counts: dict[str, int]
    affected_work_order_count: int
    affected_cluster_count: int
    skipped_work_order_count: int


class AgentDashboardValues(TypedDict):
    work_order_count: int
    multi_frequency_event_count: int
    topic_groups: list[dict[str, object]]
    handling_groups: list[dict[str, object]]
    location_groups: list[dict[str, object]]
    focus_cluster_ids: list[UUID]


class AgentRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def retrieve(
        self,
        *,
        keywords: tuple[str, ...],
        entity: str | None,
        location: str | None,
        event_type: str | None,
        work_order_ids: tuple[UUID, ...],
        created_after: datetime | None,
        created_before: datetime | None,
        limit: int,
        semantic_vector: list[float] | None,
        semantic_model_id: str | None,
    ) -> list[AgentRecord]:
        """Return a bounded, merged V2 projection, ranked by retrieval evidence."""
        terms = tuple(
            term for term in (*keywords, entity or "", location or "", event_type or "") if term
        )
        async with self._session_factory() as session:
            conditions: list[ColumnElement[bool]] = []
            if work_order_ids:
                conditions.append(WorkOrder.id.in_(work_order_ids))
            if created_after is not None:
                conditions.append(WorkOrder.created_at >= created_after)
            if created_before is not None:
                conditions.append(WorkOrder.created_at <= created_before)
            if terms:
                term_conditions: list[ColumnElement[bool]] = []
                for term in terms:
                    pattern = f"%{term}%"
                    term_conditions.append(
                        or_(
                            WorkOrder.external_work_order_number.ilike(pattern),
                            WorkOrder.raw_title.ilike(pattern),
                            WorkOrder.raw_content.ilike(pattern),
                            EventInstance.normalized_summary.ilike(pattern),
                            EventInstance.event_type.ilike(pattern),
                            sql_cast(EventInstance.location_signals, Text).ilike(pattern),
                        )
                    )
                conditions.append(or_(*term_conditions))
            statement = select(WorkOrder.id).outerjoin(
                EventInstance,
                (EventInstance.work_order_id == WorkOrder.id)
                & (EventInstance.pipeline_version == "understanding.v2"),
            )
            if conditions:
                statement = statement.where(*conditions)
            text_ids = cast(
                list[UUID],
                (await session.scalars(statement.distinct().limit(max(limit * 4, 80)))).all(),
            )
            semantic_ids = await self._semantic_ids(
                session, semantic_vector, semantic_model_id, max(limit * 3, 40)
            )
            ids = _unique_ids((*text_ids, *semantic_ids))
            if not ids and not terms and not work_order_ids:
                ids = cast(
                    list[UUID],
                    (
                        await session.scalars(
                            select(WorkOrder.id).order_by(WorkOrder.created_at.desc()).limit(limit)
                        )
                    ).all(),
                )
            return await self._projections(session, ids, terms, limit, set(semantic_ids))

    async def _semantic_ids(
        self,
        session: AsyncSession,
        vector: list[float] | None,
        model_id: str | None,
        limit: int,
    ) -> list[UUID]:
        if vector is None or model_id is None:
            return []
        distance = WorkOrderEmbedding.embedding.cosine_distance(vector).label("distance")
        rows = await session.execute(
            select(WorkOrderEmbedding.work_order_id)
            .where(
                WorkOrderEmbedding.model_id == model_id,
                WorkOrderEmbedding.dimensions == len(vector),
            )
            .order_by(distance)
            .limit(limit)
        )
        return [cast(UUID, row[0]) for row in rows.all()]

    async def _projections(
        self,
        session: AsyncSession,
        ids: Iterable[UUID],
        terms: tuple[str, ...],
        limit: int,
        semantic_ids: set[UUID] | None = None,
    ) -> list[AgentRecord]:
        id_list = _unique_ids(ids)
        if not id_list:
            return []
        work_orders = list(
            (await session.scalars(select(WorkOrder).where(WorkOrder.id.in_(id_list)))).all()
        )
        event_rows = (
            (
                await session.execute(
                    select(EventInstance)
                    .where(
                        EventInstance.work_order_id.in_(id_list),
                        EventInstance.pipeline_version == "understanding.v2",
                    )
                    .order_by(EventInstance.ordinal)
                )
            )
            .scalars()
            .all()
        )
        event_by_work_order: dict[UUID, list[EventInstance]] = {}
        for event in event_rows:
            event_by_work_order.setdefault(event.work_order_id, []).append(event)
        cluster_rows = await session.execute(
            select(EventInstance.work_order_id, EventCluster.id)
            .join(EventClusterMember, EventClusterMember.event_instance_id == EventInstance.id)
            .join(EventCluster, EventCluster.id == EventClusterMember.event_cluster_id)
            .where(EventInstance.work_order_id.in_(id_list))
        )
        clusters_by_work_order: dict[UUID, list[UUID]] = {}
        for work_order_id, cluster_id in cluster_rows.all():
            clusters_by_work_order.setdefault(work_order_id, []).append(cluster_id)
        status_map = await self._latest_statuses(session, id_list)
        results: list[AgentRecord] = []
        for work_order in work_orders:
            events = event_by_work_order.get(work_order.id, [])
            search_text = " ".join(
                [work_order.raw_title or "", work_order.raw_content]
                + [f"{event.normalized_summary} {event.event_type or ''}" for event in events]
            ).casefold()
            matched = [term for term in terms if term.casefold() in search_text]
            cluster_ids = _unique_ids(clusters_by_work_order.get(work_order.id, []))
            primary = events[0] if events else None
            results.append(
                {
                    "work_order_id": work_order.id,
                    "external_work_order_number": work_order.external_work_order_number,
                    "title": work_order.raw_title,
                    "created_at": work_order.created_at,
                    "normalized_summary": primary.normalized_summary if primary else None,
                    "location": _first_location(events),
                    "event_type": primary.event_type if primary else None,
                    "handling_status": status_map.get(work_order.id, "unhandled"),
                    "cluster_ids": cluster_ids,
                    "is_multi_frequency": bool(cluster_ids),
                    "retrieval_evidence": _evidence_labels(
                        matched, bool(events), work_order.id in (semantic_ids or set())
                    ),
                    "rank": (
                        len(matched) * 10
                        + (3 if events else 0)
                        + (2 if cluster_ids else 0)
                        + (1 if work_order.id in (semantic_ids or set()) else 0)
                    ),
                }
            )
        results.sort(key=lambda item: (item["rank"], item["created_at"]), reverse=True)
        return results[:limit]

    async def _latest_statuses(self, session: AsyncSession, ids: list[UUID]) -> dict[UUID, str]:
        records = (
            await session.scalars(
                select(WorkOrderHandlingRecord)
                .where(WorkOrderHandlingRecord.work_order_id.in_(ids))
                .order_by(WorkOrderHandlingRecord.created_at.desc())
            )
        ).all()
        result: dict[UUID, str] = {}
        for record in records:
            result.setdefault(record.work_order_id, record.new_status)
        return result

    async def create_workset(
        self,
        *,
        name: str,
        original_query: str,
        query_snapshot: dict[str, object],
        work_order_ids: tuple[UUID, ...],
        cluster_ids: tuple[UUID, ...],
        created_by: str,
    ) -> Workset:
        async with self._session_factory() as session:
            async with session.begin():
                workset = Workset(
                    name=name,
                    original_query=original_query,
                    query_snapshot=query_snapshot,
                    created_by=created_by,
                    metadata_json={"result_count": len(work_order_ids), "source": "agent"},
                )
                session.add(workset)
                await session.flush()
                session.add_all(
                    [
                        WorksetWorkOrder(workset_id=workset.id, work_order_id=item)
                        for item in _unique_ids(work_order_ids)
                    ]
                )
                session.add_all(
                    [
                        WorksetCluster(workset_id=workset.id, cluster_id=item)
                        for item in _unique_ids(cluster_ids)
                    ]
                )
                session.add(
                    AuditLog(
                        action="agent.workset_created",
                        actor_id=created_by,
                        target_type="workset",
                        target_id=str(workset.id),
                        correlation_id=None,
                        before_summary=None,
                        after_summary={
                            "work_order_count": len(work_order_ids),
                            "cluster_count": len(cluster_ids),
                        },
                        metadata_json={"original_query": original_query[:120]},
                    )
                )
            return workset

    async def get_workset(self, workset_id: UUID) -> tuple[Workset, list[UUID], list[UUID]] | None:
        async with self._session_factory() as session:
            workset = await session.get(Workset, workset_id)
            if workset is None:
                return None
            work_order_ids = list(
                (
                    await session.scalars(
                        select(WorksetWorkOrder.work_order_id).where(
                            WorksetWorkOrder.workset_id == workset_id
                        )
                    )
                ).all()
            )
            cluster_ids = list(
                (
                    await session.scalars(
                        select(WorksetCluster.cluster_id).where(
                            WorksetCluster.workset_id == workset_id
                        )
                    )
                ).all()
            )
            return workset, work_order_ids, cluster_ids

    async def create_preview(
        self,
        *,
        workset_id: UUID,
        action_type: str,
        payload: dict[str, object],
        actor_id: str,
    ) -> tuple[AgentActionPreview, AgentActionSnapshot]:
        workset = await self.get_workset(workset_id)
        if workset is None:
            raise LookupError("workset not found")
        _, work_order_ids, cluster_ids = workset
        async with self._session_factory() as session:
            status_map = await self._latest_statuses(session, work_order_ids)
            before_counts = Counter(status_map.get(item, "unhandled") for item in work_order_ids)
            snapshot: AgentActionSnapshot = {
                "work_order_ids": [str(item) for item in work_order_ids],
                "cluster_ids": [str(item) for item in cluster_ids],
                "before_status_counts": dict(before_counts),
                "affected_work_order_count": len(work_order_ids),
                "affected_cluster_count": len(cluster_ids),
                "skipped_work_order_count": 0,
            }
            preview = AgentActionPreview(
                workset_id=workset_id,
                action_type=action_type,
                payload=payload,
                preview_snapshot=snapshot,
                created_by=actor_id,
            )
            session.add(preview)
            await session.commit()
            await session.refresh(preview)
            return preview, snapshot

    async def execute_preview(self, preview_id: UUID, actor_id: str) -> tuple[str, int, str | None]:
        async with self._session_factory() as session:
            async with session.begin():
                preview = await session.get(AgentActionPreview, preview_id, with_for_update=True)
                if preview is None:
                    raise LookupError("action preview not found")
                if preview.executed_at is not None:
                    raise ValueError("action preview was already executed")
                work_order_ids = tuple(
                    UUID(value)
                    for value in _string_list(preview.preview_snapshot.get("work_order_ids"))
                )
                if preview.action_type == "export_csv":
                    output = await self._csv_for_work_orders(session, work_order_ids)
                    count = len(work_order_ids)
                else:
                    status = str(preview.payload.get("new_status") or "investigating")
                    old_statuses = await self._latest_statuses(session, list(work_order_ids))
                    now = datetime.now(UTC)
                    for work_order_id in work_order_ids:
                        session.add(
                            WorkOrderHandlingRecord(
                                work_order_id=work_order_id,
                                previous_status=old_statuses.get(work_order_id, "unhandled"),
                                new_status=status,
                                actor_id=actor_id,
                                description=_optional_text(preview.payload.get("description")),
                                result=_optional_text(preview.payload.get("result")),
                                created_at=now,
                                updated_at=now,
                            )
                        )
                    output = None
                    count = len(work_order_ids)
                preview.executed_at = datetime.now(UTC)
                session.add(
                    AuditLog(
                        action="agent.workset_batch_action_executed",
                        actor_id=actor_id,
                        target_type="workset",
                        target_id=str(preview.workset_id),
                        correlation_id=str(preview.id),
                        before_summary=preview.preview_snapshot,
                        after_summary={"executed_work_order_count": count},
                        metadata_json={"action_type": preview.action_type},
                    )
                )
                return preview.action_type, count, output

    async def dashboard(
        self, work_order_ids: tuple[UUID, ...], cluster_ids: tuple[UUID, ...]
    ) -> AgentDashboardValues:
        async with self._session_factory() as session:
            if cluster_ids and not work_order_ids:
                work_order_ids = tuple(
                    (
                        await session.scalars(
                            select(EventInstance.work_order_id)
                            .join(
                                EventClusterMember,
                                EventClusterMember.event_instance_id == EventInstance.id,
                            )
                            .where(EventClusterMember.event_cluster_id.in_(cluster_ids))
                        )
                    ).all()
                )
            projections = await self._projections(
                session, work_order_ids, (), max(len(work_order_ids), 1)
            )
            return {
                "work_order_count": len(projections),
                "multi_frequency_event_count": len(
                    _unique_ids(item for row in projections for item in row["cluster_ids"])
                ),
                "topic_groups": _counter_groups(
                    str(row["event_type"] or "未归类") for row in projections
                ),
                "handling_groups": _counter_groups(
                    str(row["handling_status"]) for row in projections
                ),
                "location_groups": _counter_groups(
                    str(row["location"] or "未提供地点") for row in projections
                ),
                "focus_cluster_ids": _unique_ids(
                    item for row in projections for item in row["cluster_ids"]
                ),
            }

    async def _csv_for_work_orders(self, session: AsyncSession, ids: tuple[UUID, ...]) -> str:
        projections = await self._projections(session, ids, (), max(len(ids), 1))
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["工单号", "标题", "处理状态", "事件摘要", "地点", "是否多频"])
        for item in projections:
            writer.writerow(
                [
                    item["external_work_order_number"] or str(item["work_order_id"]),
                    item["title"] or "",
                    item["handling_status"],
                    item["normalized_summary"] or "",
                    item["location"] or "",
                    "是" if item["is_multi_frequency"] else "否",
                ]
            )
        return output.getvalue()


def _unique_ids(values: Iterable[UUID]) -> list[UUID]:
    return list(dict.fromkeys(values))


def _first_location(events: list[EventInstance]) -> str | None:
    for event in events:
        if event.location_signals:
            return str(event.location_signals[0])
    return None


def _evidence_labels(matched: list[str], has_event: bool, is_candidate: bool) -> list[str]:
    labels = [f"关键词匹配：{term}" for term in matched]
    if has_event:
        labels.append("V2 事件摘要")
    if is_candidate and not labels:
        labels.append("pgvector 语义候选")
    return labels or ["数据库结构化记录"]


def _counter_groups(values: Iterable[str]) -> list[dict[str, object]]:
    return [{"label": label, "count": count} for label, count in Counter(values).most_common(8)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in cast(list[object], value) if isinstance(item, str)]


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
