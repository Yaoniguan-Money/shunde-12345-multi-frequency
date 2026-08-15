"""SQLAlchemy read repository for the demo catalog API."""

from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from backend.app.domain.catalog import (
    CatalogEvent,
    ClusterDetail,
    ClusterSummary,
    EntityReference,
    EventDetail,
    MatchEdgeView,
    WorkOrderDetail,
    WorkOrderSummary,
)
from backend.app.domain.ports.catalog import CatalogRepository
from backend.app.domain.types import VersionTrace
from backend.app.infrastructure.db.models import (
    CanonicalEntity,
    EventCluster,
    EventClusterMember,
    EventInstance,
    EventMatchEdge,
    WorkOrder,
)


class SQLAlchemyCatalogRepository(CatalogRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_work_orders(
        self, *, offset: int, limit: int, query: str | None
    ) -> tuple[tuple[WorkOrderSummary, ...], int]:
        async with self._session_factory() as session:
            condition = _work_order_search(query)
            total = int(
                await session.scalar(select(func.count()).select_from(WorkOrder).where(condition))
                or 0
            )
            rows = (
                await session.scalars(
                    select(WorkOrder)
                    .where(condition)
                    .order_by(WorkOrder.source_row_number)
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            return await self._summaries(session, tuple(rows)), total

    async def get_work_order(self, work_order_id: UUID) -> WorkOrderDetail | None:
        async with self._session_factory() as session:
            work_order = await session.get(WorkOrder, work_order_id)
            if work_order is None:
                return None
            summary = (await self._summaries(session, (work_order,)))[0]
            event_rows = (
                await session.scalars(
                    select(EventInstance)
                    .where(EventInstance.work_order_id == work_order.id)
                    .order_by(EventInstance.pipeline_version, EventInstance.ordinal)
                )
            ).all()
            details = await self._event_details(session, tuple(event_rows), summary)
            return WorkOrderDetail(
                summary=summary,
                import_batch_id=work_order.import_batch_id,
                raw_content=work_order.raw_content,
                raw_fields=work_order.raw_fields,
                events=details,
            )

    async def list_events(
        self,
        *,
        offset: int,
        limit: int,
        pipeline_version: str | None,
        work_order_id: UUID | None,
    ) -> tuple[tuple[EventDetail, ...], int]:
        async with self._session_factory() as session:
            condition = _event_condition(pipeline_version, work_order_id)
            join = select(EventInstance, WorkOrder).join(
                WorkOrder, WorkOrder.id == EventInstance.work_order_id
            )
            total = int(
                await session.scalar(
                    select(func.count()).select_from(EventInstance).where(condition)
                )
                or 0
            )
            rows = (
                await session.execute(
                    join.where(condition)
                    .order_by(EventInstance.created_at, EventInstance.ordinal)
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            if not rows:
                return (), total
            work_orders = tuple(row[1] for row in rows)
            events = tuple(row[0] for row in rows)
            entity_map = await self._entity_map(session, events)
            summaries = await self._summaries(session, work_orders)
            summary_by_id = {item.work_order_id: item for item in summaries}
            return (
                tuple(
                    self._event_detail(event, work_order, summary_by_id[work_order.id], entity_map)
                    for event, work_order in rows
                ),
                total,
            )

    async def get_event(self, event_id: UUID) -> EventDetail | None:
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
            summary = (await self._summaries(session, (work_order,)))[0]
            entity_map = await self._entity_map(session, (event,))
            return self._event_detail(event, work_order, summary, entity_map)

    async def list_clusters(
        self, *, offset: int, limit: int
    ) -> tuple[tuple[ClusterSummary, ...], int]:
        async with self._session_factory() as session:
            total = int(await session.scalar(select(func.count()).select_from(EventCluster)) or 0)
            clusters = (
                await session.scalars(
                    select(EventCluster)
                    .order_by(EventCluster.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            counts = await self._cluster_member_counts(
                session, tuple(cluster.id for cluster in clusters)
            )
            return (
                tuple(
                    self._cluster_summary(cluster, counts.get(cluster.id, 0))
                    for cluster in clusters
                ),
                total,
            )

    async def get_cluster(self, cluster_id: UUID) -> ClusterDetail | None:
        async with self._session_factory() as session:
            cluster = await session.get(EventCluster, cluster_id)
            if cluster is None:
                return None
            member_rows = (
                await session.execute(
                    select(EventClusterMember, EventInstance, WorkOrder)
                    .join(EventInstance, EventInstance.id == EventClusterMember.event_instance_id)
                    .join(WorkOrder, WorkOrder.id == EventInstance.work_order_id)
                    .where(EventClusterMember.event_cluster_id == cluster.id)
                    .order_by(EventInstance.work_order_id, EventInstance.ordinal)
                )
            ).all()
            events = tuple(row[1] for row in member_rows)
            entity_map = await self._entity_map(session, events)
            work_orders = tuple(row[2] for row in member_rows)
            summaries = await self._summaries(session, work_orders)
            summary_by_id = {item.work_order_id: item for item in summaries}
            members = tuple(
                self._event_detail(event, work_order, summary_by_id[work_order.id], entity_map)
                for _, event, work_order in member_rows
            )
            member_ids = tuple(event.id for event in events)
            run_ids = tuple(row[0].analysis_run_id for row in member_rows)
            edges = await self._cluster_edges(session, member_ids, run_ids)
            return ClusterDetail(
                summary=self._cluster_summary(cluster, len(members)),
                members=members,
                edges=edges,
            )

    async def _summaries(
        self, session: AsyncSession, work_orders: tuple[WorkOrder, ...]
    ) -> tuple[WorkOrderSummary, ...]:
        if not work_orders:
            return ()
        ids = tuple(row.id for row in work_orders)
        event_counts = await self._group_counts(
            session,
            select(EventInstance.work_order_id, func.count(EventInstance.id))
            .where(EventInstance.work_order_id.in_(ids))
            .group_by(EventInstance.work_order_id),
        )
        cluster_counts = await self._group_counts(
            session,
            select(
                EventInstance.work_order_id,
                func.count(func.distinct(EventClusterMember.event_cluster_id)),
            )
            .join(EventClusterMember, EventClusterMember.event_instance_id == EventInstance.id)
            .where(EventInstance.work_order_id.in_(ids))
            .group_by(EventInstance.work_order_id),
        )
        return tuple(
            WorkOrderSummary(
                work_order_id=row.id,
                external_work_order_number=row.external_work_order_number,
                source_row_number=row.source_row_number,
                raw_title=row.raw_title,
                created_at=row.created_at,
                event_count=event_counts.get(row.id, 0),
                cluster_count=cluster_counts.get(row.id, 0),
            )
            for row in work_orders
        )

    @staticmethod
    async def _group_counts(session: AsyncSession, statement: Any) -> dict[UUID, int]:
        rows = (await session.execute(statement)).all()
        return {row[0]: int(row[1]) for row in rows}

    async def _event_details(
        self,
        session: AsyncSession,
        events: tuple[EventInstance, ...],
        summary: WorkOrderSummary,
    ) -> tuple[CatalogEvent, ...]:
        entity_map = await self._entity_map(session, events)
        return tuple(
            self._catalog_event(event, summary.work_order_id, entity_map) for event in events
        )

    @staticmethod
    def _event_detail(
        event: EventInstance,
        work_order: WorkOrder,
        summary: WorkOrderSummary | None,
        entity_map: dict[UUID, EntityReference],
    ) -> EventDetail:
        if summary is None:
            summary = WorkOrderSummary(
                work_order_id=work_order.id,
                external_work_order_number=work_order.external_work_order_number,
                source_row_number=work_order.source_row_number,
                raw_title=work_order.raw_title,
                created_at=work_order.created_at,
                event_count=0,
                cluster_count=0,
            )
        catalog_event = SQLAlchemyCatalogRepository._catalog_event(event, work_order.id, entity_map)
        return EventDetail(
            event=catalog_event,
            work_order=summary,
            raw_title=work_order.raw_title,
            raw_content=work_order.raw_content,
        )

    @staticmethod
    def _catalog_event(
        event: EventInstance, work_order_id: UUID, entity_map: dict[UUID, EntityReference]
    ) -> CatalogEvent:
        event_ids = _uuid_tuple(event.entity_ids)
        return CatalogEvent(
            event_id=event.id,
            work_order_id=work_order_id,
            ordinal=event.ordinal,
            event_type=event.event_type,
            behavior=event.behavior,
            normalized_summary=event.normalized_summary,
            entities=tuple(
                entity_map.get(entity_id, EntityReference(entity_id, None, None))
                for entity_id in event_ids
            ),
            location_signals=tuple(str(value) for value in (event.location_signals or [])),
            time_signals=tuple(str(value) for value in (event.time_signals or [])),
            evidence=_evidence_items(event.evidence),
            trace=_trace(event),
        )

    async def _entity_map(
        self, session: AsyncSession, events: tuple[EventInstance, ...]
    ) -> dict[UUID, EntityReference]:
        ids = {value for event in events for value in _uuid_tuple(event.entity_ids)}
        if not ids:
            return {}
        rows = (
            await session.scalars(select(CanonicalEntity).where(CanonicalEntity.id.in_(ids)))
        ).all()
        return {row.id: EntityReference(row.id, row.standard_name, row.entity_type) for row in rows}

    async def _cluster_member_counts(
        self, session: AsyncSession, ids: tuple[UUID, ...]
    ) -> dict[UUID, int]:
        if not ids:
            return {}
        rows = (
            await session.execute(
                select(EventClusterMember.event_cluster_id, func.count(EventClusterMember.id))
                .where(EventClusterMember.event_cluster_id.in_(ids))
                .group_by(EventClusterMember.event_cluster_id)
            )
        ).all()
        return {row[0]: int(row[1]) for row in rows}

    async def _cluster_edges(
        self,
        session: AsyncSession,
        member_ids: tuple[UUID, ...],
        run_ids: tuple[UUID, ...],
    ) -> tuple[MatchEdgeView, ...]:
        if not member_ids or not run_ids:
            return ()
        rows = (
            await session.scalars(
                select(EventMatchEdge)
                .where(
                    EventMatchEdge.analysis_run_id.in_(run_ids),
                    EventMatchEdge.left_event_id.in_(member_ids),
                    EventMatchEdge.right_event_id.in_(member_ids),
                )
                .order_by(EventMatchEdge.confidence.desc())
            )
        ).all()
        return tuple(
            MatchEdgeView(
                left_event_id=row.left_event_id,
                right_event_id=row.right_event_id,
                same_event=row.same_event,
                confidence=row.confidence,
                evidence=row.evidence,
                trace=_trace(row),
            )
            for row in rows
        )

    @staticmethod
    def _cluster_summary(cluster: EventCluster, member_count: int) -> ClusterSummary:
        return ClusterSummary(
            cluster_id=cluster.id,
            name=cluster.name,
            status=cluster.status,
            confidence=cluster.confidence,
            handling_status=cluster.handling_status,
            member_count=member_count,
            evidence=cluster.evidence,
            trace=_trace(cluster),
        )


def _work_order_search(query: str | None) -> ColumnElement[bool]:
    if not query:
        return true()
    pattern = f"%{query}%"
    return or_(
        WorkOrder.external_work_order_number.ilike(pattern),
        WorkOrder.raw_title.ilike(pattern),
        WorkOrder.raw_content.ilike(pattern),
    )


def _event_condition(
    pipeline_version: str | None, work_order_id: UUID | None
) -> ColumnElement[bool]:
    conditions: list[ColumnElement[bool]] = []
    if pipeline_version:
        conditions.append(EventInstance.pipeline_version == pipeline_version)
    if work_order_id:
        conditions.append(EventInstance.work_order_id == work_order_id)
    return and_(*conditions) if conditions else true()


def _uuid_tuple(values: object) -> tuple[UUID, ...]:
    raw = cast(list[object], values) if isinstance(values, list) else []
    result: list[UUID] = []
    for value in raw:
        try:
            result.append(UUID(str(value)))
        except (TypeError, ValueError):
            continue
    return tuple(result)


def _evidence_items(value: object) -> tuple[dict[str, object], ...]:
    value_dict = cast(dict[str, object], value) if isinstance(value, dict) else {}
    raw_value = value_dict.get("items", [])
    raw = cast(list[object], raw_value) if isinstance(raw_value, list) else []
    return tuple(cast(dict[str, object], item) for item in raw if isinstance(item, dict))


def _trace(row: Any) -> VersionTrace:
    return VersionTrace(
        model_id=row.model_id,
        model_config_hash=row.model_config_hash,
        schema_version=row.schema_version,
        knowledge_snapshot_id=row.knowledge_snapshot_id,
        pipeline_version=row.pipeline_version,
        provider=row.provider,
    )
