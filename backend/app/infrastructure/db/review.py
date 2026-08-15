"""SQLAlchemy write/read adapter for audited human review commands."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.domain.catalog import ClusterReviewView, HandlingRecordView, HumanCorrectionView
from backend.app.domain.ports.review import EventReviewRepository
from backend.app.infrastructure.db.models import (
    AuditLog,
    EventCluster,
    EventClusterMember,
    EventHandlingRecord,
    EventInstance,
    HumanCorrection,
)


class SQLAlchemyEventReviewRepository(EventReviewRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add_handling_record(
        self,
        cluster_id: UUID,
        *,
        new_status: str,
        actor_id: str,
        description: str | None,
        result: str | None,
        attachment_references: tuple[str, ...],
    ) -> HandlingRecordView:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            async with session.begin():
                cluster = await session.get(EventCluster, cluster_id, with_for_update=True)
                if cluster is None:
                    raise LookupError(f"cluster not found: {cluster_id}")
                previous_status = cluster.handling_status
                cluster.handling_status = new_status
                record = EventHandlingRecord(
                    event_cluster_id=cluster.id,
                    previous_status=previous_status,
                    new_status=new_status,
                    actor_id=actor_id,
                    description=description,
                    result=result,
                    attachment_references=list(attachment_references),
                    created_at=now,
                    updated_at=now,
                )
                session.add(record)
                await session.flush()
                session.add(
                    AuditLog(
                        action="event_cluster.handling_record_added",
                        actor_id=actor_id,
                        target_type="event_cluster",
                        target_id=str(cluster.id),
                        correlation_id=None,
                        before_summary={"handling_status": previous_status},
                        after_summary={"handling_status": new_status, "record_id": str(record.id)},
                        metadata_json={"description_present": description is not None},
                        created_at=now,
                        updated_at=now,
                    )
                )
                return _handling_view(record)

    async def list_handling_records(self, cluster_id: UUID) -> tuple[HandlingRecordView, ...]:
        async with self._session_factory() as session:
            if await session.get(EventCluster, cluster_id) is None:
                raise LookupError(f"cluster not found: {cluster_id}")
            rows = (
                await session.scalars(
                    select(EventHandlingRecord)
                    .where(EventHandlingRecord.event_cluster_id == cluster_id)
                    .order_by(EventHandlingRecord.created_at)
                )
            ).all()
            return tuple(_handling_view(row) for row in rows)

    async def add_correction(
        self,
        cluster_id: UUID,
        *,
        correction_type: str,
        event_instance_id: UUID,
        actor_id: str,
        reason: str | None,
    ) -> HumanCorrectionView:
        if correction_type not in {"remove_member", "confirm_member"}:
            raise ValueError("correction_type must be remove_member or confirm_member")
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            async with session.begin():
                cluster = await session.get(EventCluster, cluster_id, with_for_update=True)
                event = await session.get(EventInstance, event_instance_id)
                if cluster is None:
                    raise LookupError(f"cluster not found: {cluster_id}")
                if event is None:
                    raise LookupError(f"event not found: {event_instance_id}")
                members = (
                    await session.scalars(
                        select(EventClusterMember)
                        .where(EventClusterMember.event_cluster_id == cluster.id)
                        .order_by(EventClusterMember.created_at)
                    )
                ).all()
                member = next(
                    (item for item in members if item.event_instance_id == event_instance_id),
                    None,
                )
                before_ids = [str(item.event_instance_id) for item in members]
                added = False
                if correction_type == "remove_member":
                    if member is None:
                        raise ValueError("event is not a member of this cluster")
                    if len(members) <= 1:
                        raise ValueError("cannot remove the last member from a cluster")
                    await session.delete(member)
                elif member is None:
                    if not members:
                        raise ValueError("cluster has no analysis membership to confirm against")
                    session.add(
                        EventClusterMember(
                            event_cluster_id=cluster.id,
                            event_instance_id=event.id,
                            analysis_run_id=members[0].analysis_run_id,
                            membership_confidence=1.0,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    added = True
                await session.flush()
                after_ids = [
                    str(item.event_instance_id)
                    for item in (
                        await session.scalars(
                            select(EventClusterMember)
                            .where(EventClusterMember.event_cluster_id == cluster.id)
                            .order_by(EventClusterMember.created_at)
                        )
                    ).all()
                ]
                payload: dict[str, object] = {
                    "action": correction_type,
                    "event_instance_id": str(event.id),
                    "member_added": added,
                }
                correction = HumanCorrection(
                    correction_type=correction_type,
                    work_order_id=event.work_order_id,
                    event_cluster_id=cluster.id,
                    supersedes_correction_id=None,
                    actor_id=actor_id,
                    reason=reason,
                    payload=payload,
                    created_at=now,
                    updated_at=now,
                )
                session.add(correction)
                await session.flush()
                session.add(
                    AuditLog(
                        action=f"event_cluster.{correction_type}",
                        actor_id=actor_id,
                        target_type="event_cluster",
                        target_id=str(cluster.id),
                        correlation_id=None,
                        before_summary={"member_event_ids": before_ids},
                        after_summary={"member_event_ids": after_ids},
                        metadata_json={"correction_id": str(correction.id)},
                        created_at=now,
                        updated_at=now,
                    )
                )
                return _correction_view(correction)

    async def list_corrections(self, cluster_id: UUID) -> tuple[HumanCorrectionView, ...]:
        async with self._session_factory() as session:
            if await session.get(EventCluster, cluster_id) is None:
                raise LookupError(f"cluster not found: {cluster_id}")
            rows = (
                await session.scalars(
                    select(HumanCorrection)
                    .where(HumanCorrection.event_cluster_id == cluster_id)
                    .order_by(HumanCorrection.created_at)
                )
            ).all()
            return tuple(_correction_view(row) for row in rows)

    async def set_review_status(
        self,
        cluster_id: UUID,
        *,
        review_status: str,
        actor_id: str,
        reason: str | None,
    ) -> ClusterReviewView:
        if review_status not in {"pending_review", "confirmed", "rejected"}:
            raise ValueError("invalid review_status")
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            async with session.begin():
                cluster = await session.get(EventCluster, cluster_id, with_for_update=True)
                if cluster is None:
                    raise LookupError(f"cluster not found: {cluster_id}")
                previous = cluster.review_status
                cluster.review_status = review_status
                session.add(
                    AuditLog(
                        action="event_cluster.review_status_changed",
                        actor_id=actor_id,
                        target_type="event_cluster",
                        target_id=str(cluster.id),
                        correlation_id=None,
                        before_summary={"review_status": previous},
                        after_summary={"review_status": review_status},
                        metadata_json={"reason": reason},
                        created_at=now,
                        updated_at=now,
                    )
                )
                return ClusterReviewView(
                    cluster_id=cluster.id,
                    previous_status=previous,
                    review_status=review_status,
                    actor_id=actor_id,
                    reason=reason,
                    reviewed_at=now,
                )


def _handling_view(row: EventHandlingRecord) -> HandlingRecordView:
    return HandlingRecordView(
        record_id=row.id,
        cluster_id=row.event_cluster_id,
        previous_status=row.previous_status,
        new_status=row.new_status,
        actor_id=row.actor_id,
        description=row.description,
        result=row.result,
        attachment_references=tuple(str(item) for item in (row.attachment_references or [])),
        created_at=row.created_at,
    )


def _correction_view(row: HumanCorrection) -> HumanCorrectionView:
    return HumanCorrectionView(
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
