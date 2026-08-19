from dataclasses import replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from backend.app.application.handlers.imports import ImportHandler, resolve_mapping
from backend.app.domain.imports import (
    ImportBatchSpec,
    ImportBatchState,
    ImportRow,
    ImportRowFailure,
    StagedSource,
    TabularDocument,
)


class InMemoryReader:
    def __init__(self, document: TabularDocument) -> None:
        self.document = document

    def read(self, path: Path, sheet_name: str | None = None) -> TabularDocument:
        return self.document


class InMemoryRepository:
    def __init__(self, initial: ImportBatchState | None = None) -> None:
        self.state = initial
        self.rows: list[ImportRow] = []
        self.failures: list[ImportRowFailure] = []
        self.start_count = 0

    async def start_or_resume(self, spec: ImportBatchSpec) -> ImportBatchState:
        self.start_count += 1
        if self.state is None:
            self.state = ImportBatchState(
                batch_id=uuid4(),
                status="running",
                checkpoint_row=0,
                total_rows=spec.total_rows,
                successful_rows=0,
                failed_rows=0,
                duplicate_rows=0,
                idempotent=False,
            )
        elif self.state.status in {"completed", "partial"}:
            self.state = replace(self.state, idempotent=True)
        return self.state

    async def persist_chunk(
        self,
        batch_id,
        rows: tuple[ImportRow, ...],
        failures: tuple[ImportRowFailure, ...],
        checkpoint_row: int,
    ) -> ImportBatchState:
        self.rows.extend(rows)
        self.failures.extend(failures)
        assert self.state is not None
        self.state = replace(
            self.state,
            checkpoint_row=checkpoint_row,
            successful_rows=self.state.successful_rows + len(rows),
            failed_rows=self.state.failed_rows + len(failures),
        )
        return self.state

    async def finish(self, batch_id) -> ImportBatchState:
        assert self.state is not None
        self.state = replace(
            self.state,
            status="partial" if self.state.failed_rows else "completed",
        )
        return self.state

    async def fail(self, batch_id, error_code: str, message: str) -> ImportBatchState:
        assert self.state is not None
        self.state = replace(self.state, status="failed")
        return self.state


def _source(tmp_path: Path) -> StagedSource:
    path = tmp_path / "source.csv"
    path.write_text("placeholder", encoding="utf-8")
    return StagedSource(path, path.name, "a" * 64, path.stat().st_size)


def test_resolve_mapping_uses_real_government_headers() -> None:
    mapping = resolve_mapping(("序号", "工单编号", "标题", "内容"))
    assert mapping.as_dict() == {
        "source_row_number": "序号",
        "external_work_order_number": "工单编号",
        "title": "标题",
        "content": "内容",
    }


async def test_import_preserves_explicit_reported_at_without_using_body_dates(
    tmp_path: Path,
) -> None:
    document = TabularDocument(
        columns=("序号", "工单编号", "受理时间", "内容"),
        total_rows=1,
        rows=((1, "250331144260109-01", "2025-03-31", "2024年6月开始欠薪"),),
    )
    repository = InMemoryRepository()

    await ImportHandler(InMemoryReader(document), repository).execute(_source(tmp_path))

    assert repository.rows[0].reported_at == datetime(2025, 3, 31)
    assert repository.rows[0].raw_fields["内容"] == "2024年6月开始欠薪"


async def test_import_keeps_raw_fields_and_continues_after_bad_row(tmp_path: Path) -> None:
    document = TabularDocument(
        columns=("序号", "工单编号", "标题", "内容"),
        total_rows=3,
        rows=(
            (1, "A-1", "标题一", "第一条内容"),
            (2, "A-2", "标题二", None),
            (3, "A-3", "标题三", "第三条内容"),
        ),
    )
    repository = InMemoryRepository()
    handler = ImportHandler(InMemoryReader(document), repository, chunk_size=2)

    result = await handler.execute(_source(tmp_path))

    assert result.status == "partial"
    assert result.successful_rows == 2
    assert result.failed_rows == 1
    assert [row.source_row_number for row in repository.rows] == [1, 3]
    assert repository.rows[0].raw_fields["内容"] == "第一条内容"
    assert len(repository.rows[0].raw_sha256) == 64
    assert repository.failures[0].error_code == "missing_content"


async def test_import_resume_skips_checkpoint_and_is_idempotent(tmp_path: Path) -> None:
    document = TabularDocument(
        columns=("序号", "内容"),
        total_rows=3,
        rows=((1, "一"), (2, "二"), (3, "三")),
    )
    batch_id = uuid4()
    repository = InMemoryRepository(ImportBatchState(batch_id, "running", 2, 3, 2, 0, 0, False))
    handler = ImportHandler(InMemoryReader(document), repository, chunk_size=10)

    result = await handler.execute(_source(tmp_path))

    assert result.status == "completed"
    assert [row.source_row_number for row in repository.rows] == [3]
    assert result.checkpoint_row == 3

    second = await handler.execute(_source(tmp_path))
    assert second.idempotent is True
    assert len(repository.rows) == 1
