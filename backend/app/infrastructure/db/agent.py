"""SQLAlchemy adapter for Agent retrieval, worksets and audited batch operations.

This module only reads V2 work-order/event/cluster projections.  It never writes
to the V2 understanding, same-event, or clustering tables.
"""

import csv
import io
import logging
import re
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import TypedDict, cast
from uuid import UUID

from sqlalchemy import Select, Text, or_, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from backend.app.domain.title_tags import parse_title_tags
from backend.app.infrastructure.db.models import (
    AgentActionPreview,
    AuditLog,
    CanonicalEntity,
    EntityMention,
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

logger = logging.getLogger(__name__)

# Vector scores are retrieval evidence, not a loose substitute for a user’s
# explicit issue constraint.  The gate permits a semantic-only match only when
# it is very strong; ordinary same-location similarity is rejected.
_ISSUE_SEMANTIC_MIN_SCORE = 0.78


class AgentRecord(TypedDict):
    work_order_id: UUID
    external_work_order_number: str | None
    title: str | None
    title_tags: list[str]
    is_urgent: bool
    created_at: datetime
    reported_at: datetime | None
    normalized_summary: str | None
    raw_content: str
    location: str | None
    location_signals: list[str]
    event_type: str | None
    handling_status: str
    cluster_ids: list[UUID]
    is_multi_frequency: bool
    retrieval_evidence: list[str]
    retrieval_trace: dict[str, object]
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
    urgent_count: int
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
        issue_terms: tuple[str, ...],
        issue_required: bool,
        entity: str | None,
        location: str | None,
        event_type: str | None,
        title_tag: str | None,
        work_order_ids: tuple[UUID, ...],
        handling_status: str | None,
        reported_after: datetime | None,
        reported_before: datetime | None,
        limit: int | None,
        semantic_vector: list[float] | None,
        semantic_model_id: str | None,
        complete_scope: bool = False,
    ) -> list[AgentRecord]:
        """Scope, recall, gate relevance, then rank the current V2 projection."""
        terms = tuple(term for term in (*keywords, event_type or "") if term)
        has_hard_scope = bool(
            location
            or entity
            or title_tag
            or work_order_ids
            or handling_status
            or reported_after is not None
            or reported_before is not None
        )
        async with self._session_factory() as session:
            scope_conditions: list[ColumnElement[bool]] = []
            if work_order_ids:
                scope_conditions.append(WorkOrder.id.in_(work_order_ids))
            # A system import timestamp is never a substitute for the business
            # complaint/acceptance timestamp.  NULL business time is excluded
            # naturally by these comparisons for a strict time query.
            if reported_after is not None:
                scope_conditions.append(WorkOrder.reported_at >= reported_after)
            if reported_before is not None:
                scope_conditions.append(WorkOrder.reported_at <= reported_before)
            if location:
                scope_conditions.append(_location_condition(location))
            if entity:
                scope_conditions.append(_entity_condition(entity))
            if handling_status:
                scope_conditions.append(_handling_status_condition(handling_status))
            if title_tag:
                scope_conditions.append(_title_tag_condition(title_tag))

            statement = (
                select(WorkOrder.id)
                .outerjoin(
                    EventInstance,
                    (EventInstance.work_order_id == WorkOrder.id)
                    & (EventInstance.pipeline_version == "understanding.v2"),
                )
                .outerjoin(EntityMention, EntityMention.work_order_id == WorkOrder.id)
                .outerjoin(CanonicalEntity, CanonicalEntity.id == EntityMention.canonical_entity_id)
            )
            if has_hard_scope:
                scoped_statement = statement.where(*scope_conditions).distinct()
                if not complete_scope:
                    scoped_statement = scoped_statement.limit(max((limit or 20) * 8, 200))
                structured_scope_ids = cast(
                    list[UUID],
                    (await session.scalars(scoped_statement)).all(),
                )
                if not structured_scope_ids:
                    return []
                semantic_scores = await self._semantic_scores(
                    session,
                    semantic_vector,
                    semantic_model_id,
                    max((limit or 20) * 3, 40),
                    allowed_work_order_ids=structured_scope_ids,
                )
                return await self._projections(
                    session,
                    _unique_ids((*structured_scope_ids, *semantic_scores)),
                    terms,
                    limit,
                    issue_terms=issue_terms,
                    issue_required=issue_required,
                    title_tag=title_tag,
                    location=location,
                    entity=entity,
                    required_work_order_ids=set(work_order_ids),
                    handling_status=handling_status,
                    semantic_scores=semantic_scores,
                )

            text_conditions = [_text_condition(term) for term in terms]
            text_ids: list[UUID] = []
            if text_conditions:
                text_ids = cast(
                    list[UUID],
                    (
                        await session.scalars(
                            _limit_statement(
                                statement.where(or_(*text_conditions)).distinct(),
                                None if complete_scope else max((limit or 20) * 4, 80),
                            )
                        )
                    ).all(),
                )
            semantic_scores = await self._semantic_scores(
                session, semantic_vector, semantic_model_id, max((limit or 20) * 3, 40)
            )
            ids = _unique_ids((*text_ids, *semantic_scores))
            if not ids and not terms:
                ids = cast(
                    list[UUID],
                    (
                        await session.scalars(
                            _limit_statement(
                                select(WorkOrder.id).order_by(WorkOrder.created_at.desc()),
                                None if complete_scope else limit,
                            )
                        )
                    ).all(),
                )
            return await self._projections(
                session,
                ids,
                terms,
                limit,
                issue_terms=issue_terms,
                issue_required=issue_required,
                title_tag=title_tag,
                semantic_scores=semantic_scores,
            )

    async def _semantic_scores(
        self,
        session: AsyncSession,
        vector: list[float] | None,
        model_id: str | None,
        limit: int,
        allowed_work_order_ids: list[UUID] | None = None,
    ) -> dict[UUID, float]:
        if vector is None or model_id is None:
            return {}
        if allowed_work_order_ids is not None and not allowed_work_order_ids:
            return {}
        distance = WorkOrderEmbedding.embedding.cosine_distance(vector).label("distance")
        statement = (
            select(WorkOrderEmbedding.work_order_id, distance)
            .where(
                WorkOrderEmbedding.model_id == model_id,
                WorkOrderEmbedding.dimensions == len(vector),
            )
            .order_by(distance)
        )
        if allowed_work_order_ids is not None:
            statement = statement.where(
                WorkOrderEmbedding.work_order_id.in_(allowed_work_order_ids)
            )
        statement = statement.limit(limit)
        rows = await session.execute(statement)
        # pgvector cosine distance is lower-is-better. Retain its normalized
        # score instead of flattening semantic recall into a boolean flag.
        return {cast(UUID, row[0]): max(0.0, min(1.0, 1.0 - float(row[1]))) for row in rows.all()}

    async def _projections(
        self,
        session: AsyncSession,
        ids: Iterable[UUID],
        terms: tuple[str, ...],
        limit: int | None,
        issue_terms: tuple[str, ...] = (),
        issue_required: bool = False,
        title_tag: str | None = None,
        location: str | None = None,
        entity: str | None = None,
        required_work_order_ids: set[UUID] | None = None,
        handling_status: str | None = None,
        semantic_scores: dict[UUID, float] | None = None,
    ) -> list[AgentRecord]:
        id_list = _unique_ids(ids)
        if not id_list:
            return []
        logger.debug(
            "Agent retrieval candidate recall complete",
            extra={"scope_candidate_count": len(id_list), "issue_required": issue_required},
        )
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
        entity_rows = await session.execute(
            select(
                EntityMention.work_order_id,
                EntityMention.mention_text,
                CanonicalEntity.standard_name,
            )
            .outerjoin(CanonicalEntity, CanonicalEntity.id == EntityMention.canonical_entity_id)
            .where(EntityMention.work_order_id.in_(id_list))
        )
        entity_text_by_work_order: dict[UUID, list[str]] = {}
        for work_order_id, mention_text, standard_name in entity_rows.all():
            entity_text_by_work_order.setdefault(work_order_id, []).extend(
                value for value in (mention_text, standard_name) if value
            )
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
            title_tags = parse_title_tags(work_order.raw_title)
            if title_tag and title_tag not in title_tags:
                continue
            entity_text = " ".join(entity_text_by_work_order.get(work_order.id, []))
            raw_search_text = " ".join(
                [work_order.raw_title or "", work_order.raw_content]
            ).casefold()
            location_signal_text = " ".join(
                signal for event in events for signal in event.location_signals
            ).casefold()
            search_text = " ".join(
                [work_order.raw_title or "", work_order.raw_content]
                + [
                    f"{event.normalized_summary} {event.event_type or ''} "
                    f"{' '.join(event.location_signals)}"
                    for event in events
                ]
                + [entity_text]
            ).casefold()
            matched = [term for term in terms if term.casefold() in search_text]
            issue_lexical_matches = [term for term in issue_terms if term.casefold() in search_text]
            event_type_match = bool(
                issue_terms
                and any(
                    term.casefold() in (event.event_type or "").casefold()
                    for term in issue_terms
                    for event in events
                )
            )
            semantic_score = (semantic_scores or {}).get(work_order.id)
            hard_location_match = bool(location) and (
                location.casefold() in raw_search_text
                or location.casefold() in location_signal_text
            )
            hard_entity_match = bool(entity) and entity.casefold() in search_text
            hard_work_order_match = (
                required_work_order_ids is None
                or not required_work_order_ids
                or work_order.id in required_work_order_ids
            )
            if location and not hard_location_match:
                continue
            if entity and not hard_entity_match:
                continue
            cluster_ids = _unique_ids(clusters_by_work_order.get(work_order.id, []))
            primary = events[0] if events else None
            current_status = status_map.get(work_order.id, "unhandled")
            if handling_status and current_status != handling_status:
                continue
            issue_relevant = bool(issue_lexical_matches or event_type_match)
            # Semantic similarity can rescue an expression mismatch, but only
            # with a meaningful score and never merely because it was top-N.
            if semantic_score is not None and semantic_score >= _ISSUE_SEMANTIC_MIN_SCORE:
                issue_relevant = True
            if issue_required and not issue_relevant:
                logger.debug(
                    "Agent relevance gate rejected candidate",
                    extra={
                        "work_order_id": str(work_order.id),
                        "location_match": hard_location_match,
                        "issue_lexical_match": bool(issue_lexical_matches),
                        "issue_semantic_score": semantic_score,
                        "event_type_match": event_type_match,
                        "reject_reason": "explicit_issue_mismatch",
                    },
                )
                continue
            results.append(
                {
                    "work_order_id": work_order.id,
                    "external_work_order_number": work_order.external_work_order_number,
                    "title": work_order.raw_title,
                    "title_tags": list(title_tags),
                    "is_urgent": "急" in title_tags,
                    "created_at": work_order.created_at,
                    "reported_at": work_order.reported_at,
                    "normalized_summary": primary.normalized_summary if primary else None,
                    "raw_content": work_order.raw_content,
                    "location": _first_location(events),
                    "location_signals": _location_signals(events),
                    "event_type": primary.event_type if primary else None,
                    "handling_status": current_status,
                    "cluster_ids": cluster_ids,
                    "is_multi_frequency": bool(cluster_ids),
                    "retrieval_evidence": _evidence_labels(
                        matched=matched,
                        location=location,
                        raw_location_match=bool(location)
                        and location.casefold() in raw_search_text,
                        v2_location_match=bool(location)
                        and location.casefold() in location_signal_text,
                        hard_entity_match=hard_entity_match,
                        hard_work_order_match=hard_work_order_match,
                        is_semantic_candidate=semantic_score is not None,
                        semantic_score=semantic_score,
                    ),
                    "rank": (
                        (1000 if hard_location_match else 0)
                        + (400 if hard_entity_match else 0)
                        + (200 if hard_work_order_match and required_work_order_ids else 0)
                        + len(issue_lexical_matches) * 100
                        + len(matched) * 20
                        + int((semantic_score or 0) * 100)
                    ),
                    "retrieval_trace": {
                        "location_match": hard_location_match,
                        "issue_lexical_match": bool(issue_lexical_matches),
                        "issue_semantic_score": semantic_score,
                        "event_type_match": event_type_match,
                        "relevance_gate_result": issue_relevant if issue_required else True,
                        "reject_reason": None,
                    },
                }
            )
        results.sort(key=lambda item: (item["rank"], item["created_at"]), reverse=True)
        logger.debug(
            "Agent relevance gate completed",
            extra={"final_evidence_count": len(results), "limit": limit},
        )
        return results if limit is None else results[:limit]

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

    async def list_worksets(
        self, *, limit: int = 24
    ) -> list[tuple[Workset, list[UUID], list[UUID]]]:
        """List recent durable worksets without relying on browser-held state."""
        async with self._session_factory() as session:
            worksets = list(
                (
                    await session.scalars(
                        select(Workset).order_by(Workset.created_at.desc()).limit(limit)
                    )
                ).all()
            )
            if not worksets:
                return []
            ids = [item.id for item in worksets]
            membership_rows = (
                await session.execute(
                    select(WorksetWorkOrder.workset_id, WorksetWorkOrder.work_order_id).where(
                        WorksetWorkOrder.workset_id.in_(ids)
                    )
                )
            ).all()
            cluster_rows = (
                await session.execute(
                    select(WorksetCluster.workset_id, WorksetCluster.cluster_id).where(
                        WorksetCluster.workset_id.in_(ids)
                    )
                )
            ).all()
            members: dict[UUID, list[UUID]] = {item.id: [] for item in worksets}
            clusters: dict[UUID, list[UUID]] = {item.id: [] for item in worksets}
            for workset_id, work_order_id in membership_rows:
                members[workset_id].append(work_order_id)
            for workset_id, cluster_id in cluster_rows:
                clusters[workset_id].append(cluster_id)
            return [(item, members[item.id], clusters[item.id]) for item in worksets]

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

    async def execute_preview(
        self, workset_id: UUID, preview_id: UUID, actor_id: str
    ) -> tuple[str, int, str | None]:
        async with self._session_factory() as session:
            async with session.begin():
                preview = await session.get(AgentActionPreview, preview_id, with_for_update=True)
                if preview is None or preview.workset_id != workset_id:
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
                "urgent_count": sum(1 for row in projections if row["is_urgent"]),
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


def _limit_statement(statement: Select[tuple[UUID]], limit: int | None) -> Select[tuple[UUID]]:
    return statement.limit(limit) if limit is not None else statement


def _first_location(events: list[EventInstance]) -> str | None:
    return _location_signals(events)[0] if _location_signals(events) else None


def _location_signals(events: list[EventInstance]) -> list[str]:
    return list(
        dict.fromkeys(
            str(signal)
            for event in events
            for signal in event.location_signals
            if str(signal).strip()
        )
    )


def _text_condition(term: str) -> ColumnElement[bool]:
    pattern = f"%{term}%"
    return or_(
        WorkOrder.external_work_order_number.ilike(pattern),
        WorkOrder.raw_title.ilike(pattern),
        WorkOrder.raw_content.ilike(pattern),
        EventInstance.normalized_summary.ilike(pattern),
        EventInstance.event_type.ilike(pattern),
        sql_cast(EventInstance.location_signals, Text).ilike(pattern),
    )


def _location_condition(location: str) -> ColumnElement[bool]:
    pattern = f"%{location}%"
    return or_(
        WorkOrder.raw_title.ilike(pattern),
        WorkOrder.raw_content.ilike(pattern),
        sql_cast(EventInstance.location_signals, Text).ilike(pattern),
    )


def _title_tag_condition(title_tag: str) -> ColumnElement[bool]:
    """SQL prefilter equivalent to the catalog's deterministic title-tag parser."""
    escaped = re.escape(title_tag)
    pattern = rf"(【\s*{escaped}\s*】|[（(]\s*{escaped}\s*[）)])"
    return WorkOrder.raw_title.op("~")(pattern)


def _entity_condition(entity: str) -> ColumnElement[bool]:
    pattern = f"%{entity}%"
    return or_(
        WorkOrder.raw_title.ilike(pattern),
        WorkOrder.raw_content.ilike(pattern),
        EventInstance.normalized_summary.ilike(pattern),
        EntityMention.mention_text.ilike(pattern),
        CanonicalEntity.standard_name.ilike(pattern),
    )


def _handling_status_condition(status: str) -> ColumnElement[bool]:
    latest_status = (
        select(WorkOrderHandlingRecord.new_status)
        .where(WorkOrderHandlingRecord.work_order_id == WorkOrder.id)
        .order_by(WorkOrderHandlingRecord.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    if status == "unhandled":
        return or_(latest_status.is_(None), latest_status == "unhandled")
    return latest_status == status


def _evidence_labels(
    *,
    matched: list[str],
    location: str | None,
    raw_location_match: bool,
    v2_location_match: bool,
    hard_entity_match: bool,
    hard_work_order_match: bool,
    is_semantic_candidate: bool,
    semantic_score: float | None,
) -> list[str]:
    labels: list[str] = []
    if location:
        labels.append(f"地点命中：{location}")
        if raw_location_match:
            labels.append("原文命中")
        if v2_location_match:
            labels.append("V2地点信号命中")
    if hard_entity_match:
        labels.append("主体硬匹配")
    if hard_work_order_match:
        labels.append("指定工单范围")
    labels.extend(f"关键词匹配：{term}" for term in matched)
    if is_semantic_candidate:
        labels.append(
            f"语义相关：{semantic_score:.2f}" if semantic_score is not None else "语义相关"
        )
    return labels or ["数据库结构化记录"]


def _counter_groups(values: Iterable[str]) -> list[dict[str, object]]:
    return [{"label": label, "count": count} for label, count in Counter(values).most_common(8)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in cast(list[object], value) if isinstance(item, str)]


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
