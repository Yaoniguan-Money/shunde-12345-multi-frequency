"""SQLAlchemy read repository for the demo catalog API."""

from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, exists, func, not_, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from backend.app.domain.catalog import (
    CatalogEvent,
    ClusterDetail,
    ClusterReference,
    ClusterSummary,
    EntityReference,
    EventDetail,
    HandlingRecordView,
    HumanCorrectionView,
    MatchEdgeView,
    WorkOrderDetail,
    WorkOrderSummary,
)
from backend.app.domain.ports.catalog import CatalogRepository
from backend.app.domain.title_tags import TITLE_TAG_WHITELIST, parse_title_tags
from backend.app.domain.types import VersionTrace
from backend.app.infrastructure.db.models import (
    CanonicalEntity,
    EventCluster,
    EventClusterMember,
    EventHandlingRecord,
    EventInstance,
    EventMatchEdge,
    HumanCorrection,
    WorkOrder,
    WorkOrderAnalysisResult,
)


class SQLAlchemyCatalogRepository(CatalogRepository):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        pipeline_version: str = "understanding.v2",
    ) -> None:
        self._session_factory = session_factory
        self._pipeline_version = pipeline_version

    async def list_work_orders(
        self,
        *,
        offset: int,
        limit: int,
        query: str | None,
        analysis_state: str | None = None,
        event_type: str | None = None,
        title_tag: str | None = None,
    ) -> tuple[tuple[WorkOrderSummary, ...], int]:
        async with self._session_factory() as session:
            condition = self._work_order_condition(
                query=query,
                analysis_state=analysis_state,
                event_type=event_type,
                title_tag=title_tag,
            )
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
                    .where(
                        EventInstance.work_order_id == work_order.id,
                        EventInstance.pipeline_version == self._pipeline_version,
                    )
                    .order_by(EventInstance.ordinal)
                )
            ).all()
            details = await self._event_details(session, tuple(event_rows), summary)
            cluster_refs = await self._cluster_refs(session, work_order.id)
            return WorkOrderDetail(
                summary=summary,
                import_batch_id=work_order.import_batch_id,
                raw_content=work_order.raw_content,
                raw_fields=work_order.raw_fields,
                events=details,
                cluster_refs=cluster_refs,
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
            condition = _event_condition(pipeline_version or self._pipeline_version, work_order_id)
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
                    .where(EventInstance.pipeline_version == self._pipeline_version)
                )
            ).first()
            if row is None:
                return None
            event, work_order = row
            summary = (await self._summaries(session, (work_order,)))[0]
            entity_map = await self._entity_map(session, (event,))
            return self._event_detail(event, work_order, summary, entity_map)

    async def event_occurrence_counts(self, pipeline_version: str | None) -> tuple[int, int]:
        version = pipeline_version or self._pipeline_version
        async with self._session_factory() as session:
            dated = int(
                await session.scalar(
                    select(func.count())
                    .select_from(EventInstance)
                    .where(
                        EventInstance.pipeline_version == version,
                        EventInstance.occurrence_date.is_not(None),
                    )
                )
                or 0
            )
            unknown = int(
                await session.scalar(
                    select(func.count())
                    .select_from(EventInstance)
                    .where(
                        EventInstance.pipeline_version == version,
                        EventInstance.occurrence_date.is_(None),
                    )
                )
                or 0
            )
            return dated, unknown

    async def list_clusters(
        self, *, offset: int, limit: int
    ) -> tuple[tuple[ClusterSummary, ...], int]:
        async with self._session_factory() as session:
            valid_ids = _valid_multi_frequency_cluster_ids(self._pipeline_version)
            total = int(
                await session.scalar(
                    select(func.count())
                    .select_from(EventCluster)
                    .where(EventCluster.id.in_(valid_ids))
                )
                or 0
            )
            clusters = (
                await session.scalars(
                    select(EventCluster)
                    .where(EventCluster.id.in_(valid_ids))
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
                    self._cluster_summary(cluster, counts.get(cluster.id, (0, 0)))
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
                    .where(EventInstance.pipeline_version == self._pipeline_version)
                    .order_by(EventInstance.work_order_id, EventInstance.ordinal)
                )
            ).all()
            work_order_count = len({row[2].id for row in member_rows})
            events = tuple(row[1] for row in member_rows)
            entity_map = await self._entity_map(session, events)
            work_order_by_id = {row[2].id: row[2] for row in member_rows}
            work_orders = tuple(work_order_by_id.values())
            summaries = await self._summaries(session, work_orders)
            summary_by_id = {item.work_order_id: item for item in summaries}
            members = tuple(
                self._event_detail(event, work_order, summary_by_id[work_order.id], entity_map)
                for _, event, work_order in member_rows
            )
            grouped_work_orders = tuple(
                WorkOrderDetail(
                    summary=summary_by_id[work_order.id],
                    import_batch_id=work_order.import_batch_id,
                    raw_content=work_order.raw_content,
                    raw_fields=work_order.raw_fields,
                    events=tuple(
                        self._catalog_event(event, work_order.id, entity_map)
                        for _, event, member_work_order in member_rows
                        if member_work_order.id == work_order.id
                    ),
                    cluster_refs=(),
                )
                for work_order in work_orders
            )
            member_ids = tuple(event.id for event in events)
            run_ids = tuple(row[0].analysis_run_id for row in member_rows)
            edges = await self._cluster_edges(session, member_ids, run_ids)
            handling_history = await self._handling_history(session, cluster.id)
            human_corrections = await self._human_corrections(session, cluster.id)
            return ClusterDetail(
                summary=self._cluster_summary(cluster, (work_order_count, len(members))),
                members=members,
                work_orders=grouped_work_orders,
                edges=edges,
                handling_history=handling_history,
                human_corrections=human_corrections,
            )

    @staticmethod
    async def _handling_history(
        session: AsyncSession, cluster_id: UUID
    ) -> tuple[HandlingRecordView, ...]:
        rows = (
            await session.scalars(
                select(EventHandlingRecord)
                .where(EventHandlingRecord.event_cluster_id == cluster_id)
                .order_by(EventHandlingRecord.created_at)
            )
        ).all()
        return tuple(
            HandlingRecordView(
                record_id=row.id,
                cluster_id=row.event_cluster_id,
                previous_status=row.previous_status,
                new_status=row.new_status,
                actor_id=row.actor_id,
                description=row.description,
                result=row.result,
                attachment_references=tuple(
                    str(item) for item in (row.attachment_references or [])
                ),
                created_at=row.created_at,
            )
            for row in rows
        )

    @staticmethod
    async def _human_corrections(
        session: AsyncSession, cluster_id: UUID
    ) -> tuple[HumanCorrectionView, ...]:
        rows = (
            await session.scalars(
                select(HumanCorrection)
                .where(HumanCorrection.event_cluster_id == cluster_id)
                .order_by(HumanCorrection.created_at)
            )
        ).all()
        return tuple(
            HumanCorrectionView(
                correction_id=row.id,
                cluster_id=row.event_cluster_id,
                work_order_id=row.work_order_id,
                correction_type=row.correction_type,
                actor_id=row.actor_id,
                reason=row.reason,
                payload=row.payload,
                supersedes_correction_id=row.supersedes_correction_id,
                created_at=row.created_at,
            )
            for row in rows
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
            .where(
                EventInstance.work_order_id.in_(ids),
                EventInstance.pipeline_version == self._pipeline_version,
            )
            .group_by(EventInstance.work_order_id),
        )
        cluster_counts = await self._group_counts(
            session,
            select(
                EventInstance.work_order_id,
                func.count(func.distinct(EventClusterMember.event_cluster_id)),
            )
            .join(EventClusterMember, EventClusterMember.event_instance_id == EventInstance.id)
            .where(
                EventInstance.work_order_id.in_(ids),
                EventInstance.pipeline_version == self._pipeline_version,
                EventClusterMember.event_cluster_id.in_(
                    _valid_multi_frequency_cluster_ids(self._pipeline_version)
                ),
            )
            .group_by(EventInstance.work_order_id),
        )
        analysis_states = await self._analysis_states(session, ids)
        return tuple(
            WorkOrderSummary(
                work_order_id=row.id,
                external_work_order_number=row.external_work_order_number,
                source_row_number=row.source_row_number,
                raw_title=row.raw_title,
                created_at=row.created_at,
                event_count=event_counts.get(row.id, 0),
                cluster_count=cluster_counts.get(row.id, 0),
                analysis_state=analysis_states.get(row.id, "unprocessed"),
                title_tags=parse_title_tags(row.raw_title),
                is_urgent="急" in parse_title_tags(row.raw_title),
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
                analysis_state="unprocessed",
                title_tags=parse_title_tags(work_order.raw_title),
                is_urgent="急" in parse_title_tags(work_order.raw_title),
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
                entity_map.get(entity_id, EntityReference(entity_id, None, None, "unresolved"))
                for entity_id in event_ids
            ),
            location_signals=tuple(str(value) for value in (event.location_signals or [])),
            time_signals=tuple(str(value) for value in (event.time_signals or [])),
            evidence=_evidence_items(event.evidence),
            trace=_trace(event),
            occurrence_date=event.occurrence_date,
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
        return {
            row.id: EntityReference(row.id, row.standard_name, row.entity_type, "resolved")
            for row in rows
        }

    async def _cluster_member_counts(
        self, session: AsyncSession, ids: tuple[UUID, ...]
    ) -> dict[UUID, tuple[int, int]]:
        if not ids:
            return {}
        rows = (
            await session.execute(
                select(
                    EventClusterMember.event_cluster_id,
                    func.count(func.distinct(EventInstance.work_order_id)),
                    func.count(EventClusterMember.id),
                )
                .join(EventInstance, EventInstance.id == EventClusterMember.event_instance_id)
                .where(EventClusterMember.event_cluster_id.in_(ids))
                .group_by(EventClusterMember.event_cluster_id)
            )
        ).all()
        return {row[0]: (int(row[1]), int(row[2])) for row in rows}

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
    def _cluster_summary(cluster: EventCluster, counts: tuple[int, int]) -> ClusterSummary:
        work_order_count, event_count = counts
        return ClusterSummary(
            cluster_id=cluster.id,
            name=cluster.name,
            status=cluster.status,
            confidence=cluster.confidence,
            handling_status=cluster.handling_status,
            member_count=work_order_count,
            work_order_count=work_order_count,
            event_count=event_count,
            evidence=cluster.evidence,
            trace=_trace(cluster),
            review_status=cluster.review_status,
            is_multi_frequency=work_order_count >= 2,
        )

    async def _analysis_states(
        self, session: AsyncSession, work_order_ids: tuple[UUID, ...]
    ) -> dict[UUID, str]:
        rows = (
            await session.scalars(
                select(WorkOrderAnalysisResult)
                .where(
                    WorkOrderAnalysisResult.work_order_id.in_(work_order_ids),
                    WorkOrderAnalysisResult.pipeline_version == self._pipeline_version,
                )
                .order_by(
                    WorkOrderAnalysisResult.work_order_id,
                    WorkOrderAnalysisResult.analyzed_at.desc(),
                )
            )
        ).all()
        result: dict[UUID, str] = {}
        for row in rows:
            result.setdefault(row.work_order_id, row.status)
        return result

    async def _cluster_refs(
        self, session: AsyncSession, work_order_id: UUID
    ) -> tuple[ClusterReference, ...]:
        rows = (
            await session.scalars(
                select(EventCluster)
                .join(EventClusterMember, EventClusterMember.event_cluster_id == EventCluster.id)
                .join(EventInstance, EventInstance.id == EventClusterMember.event_instance_id)
                .where(
                    EventInstance.work_order_id == work_order_id,
                    EventInstance.pipeline_version == self._pipeline_version,
                    EventCluster.id.in_(_valid_multi_frequency_cluster_ids(self._pipeline_version)),
                )
                .distinct()
                .order_by(EventCluster.created_at.desc())
            )
        ).all()
        return tuple(
            ClusterReference(
                cluster_id=row.id,
                cluster_name=row.name,
                review_status=row.review_status,
                handling_status=row.handling_status,
            )
            for row in rows
        )

    def _work_order_condition(
        self,
        *,
        query: str | None,
        analysis_state: str | None,
        event_type: str | None,
        title_tag: str | None,
    ) -> ColumnElement[bool]:
        conditions: list[ColumnElement[bool]] = [_work_order_search(query)]
        latest_state = (
            select(WorkOrderAnalysisResult.status)
            .where(
                WorkOrderAnalysisResult.work_order_id == WorkOrder.id,
                WorkOrderAnalysisResult.pipeline_version == self._pipeline_version,
            )
            .order_by(WorkOrderAnalysisResult.analyzed_at.desc())
            .limit(1)
            .scalar_subquery()
        )
        if analysis_state == "unprocessed":
            conditions.append(latest_state.is_(None))
        elif analysis_state in {"analyzed", "analyzed_no_event", "failed"}:
            conditions.append(latest_state == analysis_state)
        elif analysis_state is not None:
            conditions.append(not_(true()))
        if event_type:
            conditions.append(
                exists(
                    select(EventInstance.id).where(
                        EventInstance.work_order_id == WorkOrder.id,
                        EventInstance.pipeline_version == self._pipeline_version,
                        EventInstance.event_type == event_type,
                    )
                )
            )
        if title_tag:
            conditions.append(_title_tag_condition(title_tag))
        return and_(*conditions)


def _valid_multi_frequency_cluster_ids(pipeline_version: str):
    return (
        select(EventClusterMember.event_cluster_id)
        .join(EventInstance, EventInstance.id == EventClusterMember.event_instance_id)
        .where(EventInstance.pipeline_version == pipeline_version)
        .group_by(EventClusterMember.event_cluster_id)
        .having(func.count(func.distinct(EventInstance.work_order_id)) >= 2)
    )


def _title_tag_condition(title_tag: str) -> ColumnElement[bool]:
    if title_tag not in TITLE_TAG_WHITELIST:
        return not_(true())
    title = func.coalesce(WorkOrder.raw_title, "")
    return or_(
        title.contains(f"【{title_tag}】"),
        title.contains(f"（{title_tag}）"),
        title.contains(f"({title_tag})"),
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
