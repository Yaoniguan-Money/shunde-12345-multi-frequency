"""CSV exporter for the multi-frequency event detail contract."""

import csv
import io
from collections.abc import Sequence
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.domain.types import ExportArtifact, ExportRequest
from backend.app.infrastructure.db.models import (
    CanonicalEntity,
    EventCluster,
    EventClusterMember,
    EventHandlingRecord,
    EventInstance,
    WorkOrder,
)

ExportRow = tuple[EventCluster, EventClusterMember, EventInstance, WorkOrder]


class SQLAlchemyCSVExporter:
    """Export persisted cluster projections without touching raw source data."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def export(self, request: ExportRequest) -> ExportArtifact:
        async with self._session_factory() as session:
            statement = (
                select(EventCluster, EventClusterMember, EventInstance, WorkOrder)
                .join(
                    EventClusterMember,
                    EventClusterMember.event_cluster_id == EventCluster.id,
                )
                .join(EventInstance, EventInstance.id == EventClusterMember.event_instance_id)
                .join(WorkOrder, WorkOrder.id == EventInstance.work_order_id)
                .order_by(EventCluster.created_at, EventClusterMember.created_at)
            )
            if request.event_cluster_ids:
                statement = statement.where(EventCluster.id.in_(request.event_cluster_ids))
            rows = cast(
                Sequence[ExportRow],
                (await session.execute(statement)).all(),
            )
            if request.event_cluster_ids and not rows:
                raise LookupError("no exportable multi-frequency event found")
            cluster_ids = tuple(dict.fromkeys(row[0].id for row in rows))
            handling = await self._latest_handling(session, cluster_ids)
            entity_map = await self._entity_names(session, rows)

        output = io.StringIO(newline="")
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "cluster_id",
                "cluster_name",
                "work_order_number",
                "title",
                "event_id",
                "event_summary",
                "subject",
                "location",
                "ai_evidence",
                "handling_status",
                "handling_result",
            ],
        )
        writer.writeheader()
        for cluster, _member, event, work_order in rows:
            writer.writerow(
                {
                    "cluster_id": str(cluster.id),
                    "cluster_name": cluster.name,
                    "work_order_number": work_order.external_work_order_number or "",
                    "title": work_order.raw_title or "",
                    "event_id": str(event.id),
                    "event_summary": event.normalized_summary,
                    "subject": "; ".join(
                        entity_map.get(value, value) for value in _uuid_strings(event.entity_ids)
                    ),
                    "location": "; ".join(str(value) for value in (event.location_signals or [])),
                    "ai_evidence": _ai_evidence(event),
                    "handling_status": cluster.handling_status,
                    "handling_result": handling.get(cluster.id, ""),
                }
            )
        return ExportArtifact(
            filename="multi-frequency-events.csv",
            media_type="text/csv; charset=utf-8",
            content=output.getvalue().encode("utf-8-sig"),
        )

    @staticmethod
    async def _latest_handling(
        session: AsyncSession, cluster_ids: tuple[UUID, ...]
    ) -> dict[UUID, str]:
        if not cluster_ids:
            return {}
        rows = (
            await session.scalars(
                select(EventHandlingRecord)
                .where(EventHandlingRecord.event_cluster_id.in_(cluster_ids))
                .order_by(EventHandlingRecord.created_at)
            )
        ).all()
        return {row.event_cluster_id: row.result or "" for row in rows}

    @staticmethod
    async def _entity_names(session: AsyncSession, rows: Sequence[ExportRow]) -> dict[str, str]:
        ids = {value for _, _, event, _ in rows for value in _uuid_strings(event.entity_ids)}
        if not ids:
            return {}
        entities = (
            await session.scalars(select(CanonicalEntity).where(CanonicalEntity.id.in_(ids)))
        ).all()
        return {str(entity.id): entity.standard_name for entity in entities}


def _uuid_strings(values: object) -> tuple[str, ...]:
    raw = cast(list[object], values) if isinstance(values, list) else []
    result: list[str] = []
    for value in raw:
        try:
            result.append(str(UUID(str(value))))
        except (TypeError, ValueError):
            continue
    return tuple(result)


def _ai_evidence(event: EventInstance) -> str:
    evidence = event.evidence or {}
    raw_items = evidence.get("items", [])
    items = cast(list[object], raw_items) if isinstance(raw_items, list) else []
    quotes = [
        str(cast(dict[str, object], item).get("quote"))
        for item in items
        if isinstance(item, dict) and cast(dict[str, object], item).get("quote")
    ]
    trace = (
        f"provider={event.provider or ''};model={event.model_id or ''};"
        f"schema={event.schema_version};pipeline={event.pipeline_version}"
    )
    return f"{' | '.join(quotes)} [{trace}]"
