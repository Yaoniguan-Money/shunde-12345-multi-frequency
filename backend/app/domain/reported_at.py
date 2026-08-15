from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from backend.app.domain.imports import ImportRow


class ReportedAtSource(StrEnum):
    FIELD_MAPPING = "field_mapping"
    WORK_ORDER_NUMBER = "work_order_number"
    UNKNOWN = "unknown"


PARSER_VERSION = "reported_at.v1"


@dataclass(frozen=True, slots=True)
class ReportedAtResult:
    reported_at: datetime | None
    source: ReportedAtSource
    parser_version: str

    @property
    def is_resolved(self) -> bool:
        return self.reported_at is not None


class WorkOrderNumberDateParser(Protocol):
    def parse(self, work_order_number: str | None) -> datetime | None: ...


class ReportedAtResolver:
    def __init__(self, wro_number_parser: WorkOrderNumberDateParser) -> None:
        self._wro_number_parser = wro_number_parser

    def resolve(self, row: ImportRow) -> ReportedAtResult:
        field_value = row.raw_fields.get("reported_at")
        if isinstance(field_value, (datetime, str)):
            parsed = self._try_parse_datetime(field_value)
            if parsed is not None:
                return ReportedAtResult(
                    reported_at=parsed,
                    source=ReportedAtSource.FIELD_MAPPING,
                    parser_version=PARSER_VERSION,
                )

        wro_number_date = self._wro_number_parser.parse(row.external_work_order_number)
        if wro_number_date is not None:
            return ReportedAtResult(
                reported_at=wro_number_date,
                source=ReportedAtSource.WORK_ORDER_NUMBER,
                parser_version=PARSER_VERSION,
            )

        return ReportedAtResult(
            reported_at=None,
            source=ReportedAtSource.UNKNOWN,
            parser_version=PARSER_VERSION,
        )

    @staticmethod
    def _try_parse_datetime(value: object) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            for fmt in (
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d %H:%M",
                "%Y/%m/%d",
            ):
                try:
                    return datetime.strptime(value.strip(), fmt)
                except ValueError:
                    continue
        return None
