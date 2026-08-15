"""Application commands for audited event handling and human corrections."""

from uuid import UUID

from backend.app.domain.catalog import HandlingRecordView, HumanCorrectionView
from backend.app.domain.ports.review import EventReviewRepository


class ReviewCommandError(ValueError):
    """A human review command is invalid for the current cluster state."""


class EventReviewService:
    def __init__(self, repository: EventReviewRepository) -> None:
        self._repository = repository

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
        return await self._repository.add_handling_record(
            cluster_id,
            new_status=new_status,
            actor_id=actor_id,
            description=description,
            result=result,
            attachment_references=attachment_references,
        )

    async def list_handling_records(self, cluster_id: UUID) -> tuple[HandlingRecordView, ...]:
        return await self._repository.list_handling_records(cluster_id)

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
            raise ReviewCommandError("correction_type must be remove_member or confirm_member")
        return await self._repository.add_correction(
            cluster_id,
            correction_type=correction_type,
            event_instance_id=event_instance_id,
            actor_id=actor_id,
            reason=reason,
        )

    async def list_corrections(self, cluster_id: UUID) -> tuple[HumanCorrectionView, ...]:
        return await self._repository.list_corrections(cluster_id)
