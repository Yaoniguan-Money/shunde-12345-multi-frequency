import hashlib
import io
from pathlib import Path
from uuid import uuid4

import polars as pl
from fastapi import UploadFile

from backend.app.domain.imports import StagedSource, TabularDocument


class PolarsTabularReader:
    def read(self, path: Path, sheet_name: str | None = None) -> TabularDocument:
        suffix = path.suffix.casefold()
        if suffix in {".xlsx", ".xls"}:
            frame = pl.read_excel(
                path,
                sheet_name=sheet_name or "Sheet1",
                engine="calamine",
                raise_if_empty=False,
            )
        elif suffix == ".csv":
            frame = self._read_csv(path)
        else:
            raise ValueError("仅支持 .xlsx、.xls、.csv 文件")
        columns = tuple(str(column) for column in frame.columns)
        if len(set(columns)) != len(columns):
            raise ValueError("源文件存在重复表头，无法安全建立字段映射")
        return TabularDocument(columns, frame.height, frame.iter_rows())

    @staticmethod
    def _read_csv(path: Path) -> pl.DataFrame:
        raw = path.read_bytes()
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                text = raw.decode(encoding)
                return pl.read_csv(
                    io.StringIO(text),
                    try_parse_dates=False,
                    infer_schema_length=1000,
                )
            except UnicodeDecodeError:
                continue
        raise ValueError("CSV 编码不是 UTF-8/GB18030，无法安全读取")


class SourceStager:
    _allowed_extensions = {".xlsx", ".xls", ".csv"}

    def __init__(self, runtime_dir: Path) -> None:
        self._root = runtime_dir / "imports"
        self._root.mkdir(parents=True, exist_ok=True)

    def stage_path(self, path: Path, filename: str | None = None) -> StagedSource:
        source_name = Path(filename or path.name).name
        self._validate_extension(source_name)
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        return StagedSource(path, source_name, digest.hexdigest(), size)

    async def stage_upload(self, upload: UploadFile) -> StagedSource:
        filename = Path(upload.filename or "upload.xlsx").name
        self._validate_extension(filename)
        destination = self._root / f"{uuid4().hex}{Path(filename).suffix.casefold()}"
        digest = hashlib.sha256()
        size = 0
        try:
            with destination.open("wb") as target:
                while chunk := await upload.read(1024 * 1024):
                    digest.update(chunk)
                    target.write(chunk)
                    size += len(chunk)
            return StagedSource(destination, filename, digest.hexdigest(), size)
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    @classmethod
    def _validate_extension(cls, filename: str) -> None:
        extension = Path(filename).suffix.casefold()
        if extension not in cls._allowed_extensions:
            allowed = ", ".join(sorted(cls._allowed_extensions))
            raise ValueError(f"不支持的文件类型 {extension or '<none>'}；仅支持 {allowed}")
