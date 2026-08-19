import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime

from backend.app.domain.imports import (
    ImportBatchSpec,
    ImportBatchState,
    ImportField,
    ImportMapping,
    ImportRow,
    ImportRowFailure,
    ImportScalar,
    ImportSummary,
    StagedSource,
    TabularDocument,
)
from backend.app.domain.ports.imports import ImportBatchRepository, TabularReader


class ImportMappingError(ValueError):
    """The source columns cannot satisfy the requested canonical mapping."""


class ImportRowValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ImportPreview:
    columns: tuple[str, ...]
    total_rows: int
    suggested_mapping: ImportMapping


_ALIASES: dict[ImportField, tuple[str, ...]] = {
    ImportField.SOURCE_ROW_NUMBER: (
        "序号",
        "行号",
        "记录号",
        "row",
        "row_number",
        "source_row_number",
    ),
    ImportField.EXTERNAL_WORK_ORDER_NUMBER: (
        "工单编号",
        "工单号",
        "工单id",
        "work_order_number",
        "external_work_order_number",
    ),
    ImportField.TITLE: ("标题", "主题", "主题概括", "title", "subject"),
    ImportField.CONTENT: ("内容", "工单内容", "正文", "content", "description", "text"),
    ImportField.REPORTED_AT: (
        "受理时间",
        "受理日期",
        "投诉时间",
        "投诉日期",
        "上报时间",
        "上报日期",
        "reported_at",
    ),
}


def _normalize_header(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).replace("\ufeff", "")
    return re.sub(r"[\s_\-]+", "", normalized).strip().casefold()


def _column_lookup(columns: tuple[str, ...]) -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = {}
    for column in columns:
        lookup.setdefault(_normalize_header(column), []).append(column)
    return lookup


def _find_column(
    field: ImportField, columns: tuple[str, ...], lookup: dict[str, list[str]]
) -> str | None:
    candidates: list[str] = []
    for alias in _ALIASES[field]:
        candidates.extend(lookup.get(_normalize_header(alias), []))
    unique = list(dict.fromkeys(candidates))
    if len(unique) > 1:
        raise ImportMappingError(
            f"字段 {field.value} 自动映射有多个候选: {', '.join(unique)}；请提供显式 mapping"
        )
    return unique[0] if unique else None


def resolve_mapping(
    columns: tuple[str, ...], requested: dict[str, str] | None = None
) -> ImportMapping:
    requested = requested or {}
    lookup = _column_lookup(columns)
    by_normalized = {_normalize_header(column): column for column in columns}
    resolved: dict[ImportField, str | None] = {}
    for field in ImportField:
        requested_column = requested.get(field.value)
        if requested_column is not None:
            actual = by_normalized.get(_normalize_header(requested_column))
            if actual is None:
                raise ImportMappingError(f"字段 {field.value} 指定的源列不存在: {requested_column}")
            resolved[field] = actual
        else:
            resolved[field] = _find_column(field, columns, lookup)
    content = resolved[ImportField.CONTENT]
    if content is None:
        raise ImportMappingError("缺少必需字段 content；请映射到源文件中的内容/正文列")
    return ImportMapping(
        source_row_number=resolved[ImportField.SOURCE_ROW_NUMBER],
        external_work_order_number=resolved[ImportField.EXTERNAL_WORK_ORDER_NUMBER],
        title=resolved[ImportField.TITLE],
        content=content,
        reported_at=resolved[ImportField.REPORTED_AT],
    )


def _json_scalar(value: object) -> ImportScalar:
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return value
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    return str(value)


def _text(value: ImportScalar) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _source_row_number(value: ImportScalar, fallback: int) -> int:
    if value is None or (isinstance(value, str) and not value.strip()):
        return fallback
    if isinstance(value, bool):
        raise ImportRowValidationError("invalid_source_row_number", "序号不能是布尔值")
    try:
        parsed = float(str(value).strip())
    except ValueError as error:
        raise ImportRowValidationError("invalid_source_row_number", "序号不是整数") from error
    if not parsed.is_integer() or parsed < 1:
        raise ImportRowValidationError("invalid_source_row_number", "序号必须是正整数")
    return int(parsed)


def _reported_at(value: ImportScalar) -> datetime | None:
    """Parse only an explicit source acceptance/report timestamp.

    A blank value remains unknown; event-body dates and import timestamps are
    never used as a substitute.
    """

    text = _text(value)
    if text is None:
        return None
    normalized = text.replace("年", "-").replace("月", "-").replace("日", "").strip()
    normalized = normalized.replace("/", "-")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ImportRowValidationError("invalid_reported_at", "受理/投诉时间格式无效") from error


def _raw_hash(raw_fields: dict[str, ImportScalar]) -> str:
    payload = json.dumps(raw_fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_row(
    columns: tuple[str, ...],
    values: tuple[ImportScalar, ...],
    mapping: ImportMapping,
    physical_row: int,
) -> ImportRow:
    raw_fields = {
        column: _json_scalar(values[index] if index < len(values) else None)
        for index, column in enumerate(columns)
    }
    try:
        row_number_value = (
            raw_fields.get(mapping.source_row_number) if mapping.source_row_number else None
        )
        source_row_number = _source_row_number(row_number_value, physical_row)
        content = _text(raw_fields.get(mapping.content))
        if content is None:
            raise ImportRowValidationError("missing_content", "内容不能为空")
    except ImportRowValidationError:
        raise
    external_number = (
        _text(raw_fields.get(mapping.external_work_order_number))
        if mapping.external_work_order_number
        else None
    )
    title = _text(raw_fields.get(mapping.title)) if mapping.title else None
    reported_at = _reported_at(raw_fields.get(mapping.reported_at)) if mapping.reported_at else None
    return ImportRow(
        source_row_number=source_row_number,
        external_work_order_number=external_number,
        title=title,
        content=content,
        reported_at=reported_at,
        raw_fields=raw_fields,
        raw_sha256=_raw_hash(raw_fields),
    )


class ImportHandler:
    def __init__(
        self,
        reader: TabularReader,
        repository: ImportBatchRepository,
        chunk_size: int = 1000,
    ) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        self._reader = reader
        self._repository = repository
        self._chunk_size = chunk_size

    def preview(self, source: StagedSource, sheet_name: str | None = None) -> ImportPreview:
        document = self._reader.read(source.path, sheet_name)
        mapping = resolve_mapping(document.columns)
        return ImportPreview(document.columns, document.total_rows, mapping)

    async def execute(
        self,
        source: StagedSource,
        mapping: dict[str, str] | None = None,
        sheet_name: str | None = None,
    ) -> ImportSummary:
        document = self._reader.read(source.path, sheet_name)
        resolved_mapping = resolve_mapping(document.columns, mapping)
        spec = ImportBatchSpec(
            filename=source.filename,
            source_sha256=source.sha256,
            source_size_bytes=source.size_bytes,
            sheet_name=sheet_name,
            mapping=resolved_mapping,
            total_rows=document.total_rows,
        )
        state = await self._repository.start_or_resume(spec)
        if state.idempotent:
            return self._summary(state)
        try:
            await self._consume(document, resolved_mapping, state)
            return self._summary(await self._repository.finish(state.batch_id))
        except Exception as error:
            failed = await self._repository.fail(
                state.batch_id, "import_failed", "导入任务失败，请根据日志和批次状态恢复"
            )
            if isinstance(error, ImportMappingError):
                raise
            raise RuntimeError(
                f"import failed for batch {failed.batch_id}; checkpoint={failed.checkpoint_row}"
            ) from error

    async def _consume(
        self, document: TabularDocument, mapping: ImportMapping, state: ImportBatchState
    ) -> None:
        rows: list[ImportRow] = []
        failures: list[ImportRowFailure] = []
        for physical_row, values in enumerate(document.rows, start=1):
            if physical_row <= state.checkpoint_row:
                continue
            try:
                rows.append(_validate_row(document.columns, values, mapping, physical_row))
            except ImportRowValidationError as error:
                failures.append(ImportRowFailure(physical_row, error.code, str(error)))
            if len(rows) + len(failures) >= self._chunk_size:
                state = await self._repository.persist_chunk(
                    state.batch_id, tuple(rows), tuple(failures), physical_row
                )
                rows.clear()
                failures.clear()
        if rows or failures:
            await self._repository.persist_chunk(
                state.batch_id, tuple(rows), tuple(failures), document.total_rows
            )

    @staticmethod
    def _summary(state: ImportBatchState) -> ImportSummary:
        return ImportSummary(
            batch_id=state.batch_id,
            status=state.status,
            total_rows=state.total_rows,
            successful_rows=state.successful_rows,
            failed_rows=state.failed_rows,
            duplicate_rows=state.duplicate_rows,
            checkpoint_row=state.checkpoint_row,
            idempotent=state.idempotent,
        )
