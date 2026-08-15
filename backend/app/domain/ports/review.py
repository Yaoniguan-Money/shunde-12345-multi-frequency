"""Write-side ports for audited human handling and corrections."""

from typing import Protocol
from uuid import UUID

from backend.app.domain.catalog import HandlingRecordView, HumanCorrectionView


class EventReviewRepository(Protocol):
    async def add_handling_record(
        self,
        cluster_id: UUID,
        *,
        new_status: str,
        actor_id: str,
        description: str | None,
        result: str | None,
        attachment_references: tuple[str, ...],
    ) -> HandlingRecordView: ...

    async def list_handling_records(self, cluster_id: UUID) -> tuple[HandlingRecordView, ...]: ...

    async def add_correction(
        self,
        cluster_id: UUID,
        *,
        correction_type: str,
        event_instance_id: UUID,
        actor_id: str,
        reason: str | None,
    ) -> HumanCorrectionView: ...

    async def list_corrections(self, cluster_id: UUID) -> tuple[HumanCorrectionView, ...]: ...
