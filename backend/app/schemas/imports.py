from uuid import UUID

from pydantic import BaseModel, field_validator


class ImportMappingRequest(BaseModel):
    source_row_number: str | None = None
    external_work_order_number: str | None = None
    title: str | None = None
    content: str | None = None
    reported_at: str | None = None

    @field_validator(
        "source_row_number", "external_work_order_number", "title", "content", "reported_at"
    )
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def as_mapping(self) -> dict[str, str]:
        return self.model_dump(exclude_none=True)


class ImportPreviewResponse(BaseModel):
    columns: tuple[str, ...]
    total_rows: int
    suggested_mapping: dict[str, str]


class ImportResponse(BaseModel):
    batch_id: UUID
    status: str
    total_rows: int
    successful_rows: int
    failed_rows: int
    duplicate_rows: int
    checkpoint_row: int
    idempotent: bool
