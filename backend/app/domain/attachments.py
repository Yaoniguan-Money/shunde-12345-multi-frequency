from collections.abc import AsyncIterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AttachmentMetadata:
    attachment_id: UUID
    reference: str
    original_filename: str
    size: int
    content_type: str


@dataclass(frozen=True, slots=True)
class StoredAttachment:
    metadata: AttachmentMetadata
    path: Path


class AttachmentStore(Protocol):
    async def save(
        self, filename: str, content_type: str, chunks: AsyncIterable[bytes]
    ) -> AttachmentMetadata: ...

    async def get(self, attachment_id: UUID) -> StoredAttachment | None: ...
