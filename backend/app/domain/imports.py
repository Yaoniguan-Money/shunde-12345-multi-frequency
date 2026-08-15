from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from uuid import UUID

ImportScalar = str | int | float | bool | None
ImportRowFields = Mapping[str, ImportScalar]


class ImportField(StrEnum):
    SOURCE_ROW_NUMBER = "source_row_number"
    EXTERNAL_WORK_ORDER_NUMBER = "external_work_order_number"
    TITLE = "title"
    CONTENT = "content"


@dataclass(frozen=True, slots=True)
class StagedSource:
    path: Path
    filename: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class TabularDocument:
    columns: tuple[str, ...]
    total_rows: int
    rows: Iterable[tuple[ImportScalar, ...]]


@dataclass(frozen=True, slots=True)
class ImportMapping:
    source_row_number: str | None
    external_work_order_number: str | None
    title: str | None
    content: str

    def as_dict(self) -> dict[str, str]:
        values = {ImportField.CONTENT.value: self.content}
        optional = {
            ImportField.SOURCE_ROW_NUMBER.value: self.source_row_number,
            ImportField.EXTERNAL_WORK_ORDER_NUMBER.value: self.external_work_order_number,
            ImportField.TITLE.value: self.title,
        }
        values.update({key: value for key, value in optional.items() if value is not None})
        return values


@dataclass(frozen=True, slots=True)
class ImportRow:
    source_row_number: int
    external_work_order_number: str | None
    title: str | None
    content: str
    raw_fields: dict[str, ImportScalar]
    raw_sha256: str
    reported_at: datetime | None = None
    reported_at_source: str | None = None
    reported_at_parser_version: str | None = None
    source_tags: tuple[str, ...] = ()
    raw_payload_hash: str | None = None


@dataclass(frozen=True, slots=True)
class ImportRowFailure:
    source_row_number: int
    error_code: str
    message: str


@dataclass(frozen=True, slots=True)
class ImportBatchSpec:
    filename: str
    source_sha256: str
    source_size_bytes: int
    sheet_name: str | None
    mapping: ImportMapping
    total_rows: int


@dataclass(frozen=True, slots=True)
class ImportBatchState:
    batch_id: UUID
    status: str
    checkpoint_row: int
    total_rows: int
    successful_rows: int
    failed_rows: int
    duplicate_rows: int
    idempotent: bool


@dataclass(frozen=True, slots=True)
class ImportSummary:
    batch_id: UUID
    status: str
    total_rows: int
    successful_rows: int
    failed_rows: int
    duplicate_rows: int
    checkpoint_row: int
    idempotent: bool


class TabularReader(Protocol):
    def read(self, path: Path, sheet_name: str | None = None) -> TabularDocument: ...


class ImportBatchRepository(Protocol):
    async def start_or_resume(self, spec: ImportBatchSpec) -> ImportBatchState: ...

    async def persist_chunk(
        self,
        batch_id: UUID,
        rows: tuple[ImportRow, ...],
        failures: tuple[ImportRowFailure, ...],
        checkpoint_row: int,
    ) -> ImportBatchState: ...

    async def finish(self, batch_id: UUID) -> ImportBatchState: ...

    async def fail(self, batch_id: UUID, error_code: str, message: str) -> ImportBatchState: ...
