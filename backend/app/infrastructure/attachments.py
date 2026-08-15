"""Bounded local runtime attachment storage for the single-machine Demo."""

import json
import re
from collections.abc import AsyncIterable
from pathlib import Path
from uuid import UUID, uuid4

from backend.app.domain.attachments import AttachmentMetadata, StoredAttachment


class LocalAttachmentStore:
    def __init__(self, root: Path, max_bytes: int) -> None:
        self._root = root.resolve()
        self._max_bytes = max_bytes
        self._root.mkdir(parents=True, exist_ok=True)

    async def save(
        self, filename: str, content_type: str, chunks: AsyncIterable[bytes]
    ) -> AttachmentMetadata:
        safe_name = _safe_filename(filename)
        attachment_id = uuid4()
        data_path = self._path(attachment_id, ".bin")
        metadata_path = self._path(attachment_id, ".json")
        size = 0
        try:
            with data_path.open("xb") as output:
                async for chunk in chunks:
                    size += len(chunk)
                    if size > self._max_bytes:
                        raise ValueError(f"attachment exceeds {self._max_bytes} byte limit")
                    output.write(chunk)
            metadata = AttachmentMetadata(
                attachment_id=attachment_id,
                reference=str(attachment_id),
                original_filename=safe_name,
                size=size,
                content_type=content_type or "application/octet-stream",
            )
            metadata_path.write_text(
                json.dumps(
                    {
                        "attachment_id": str(metadata.attachment_id),
                        "original_filename": metadata.original_filename,
                        "size": metadata.size,
                        "content_type": metadata.content_type,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            return metadata
        except Exception:
            data_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
            raise

    async def get(self, attachment_id: UUID) -> StoredAttachment | None:
        data_path = self._path(attachment_id, ".bin")
        metadata_path = self._path(attachment_id, ".json")
        if not data_path.is_file() or not metadata_path.is_file():
            return None
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata = AttachmentMetadata(
            attachment_id=attachment_id,
            reference=str(attachment_id),
            original_filename=_safe_filename(str(payload["original_filename"])),
            size=int(payload["size"]),
            content_type=str(payload["content_type"]),
        )
        if data_path.stat().st_size != metadata.size:
            raise RuntimeError("attachment metadata size mismatch")
        return StoredAttachment(metadata, data_path)

    def _path(self, attachment_id: UUID, suffix: str) -> Path:
        path = (self._root / f"{attachment_id}{suffix}").resolve()
        if path.parent != self._root:
            raise ValueError("invalid attachment path")
        return path


def _safe_filename(value: str) -> str:
    name = Path(value).name
    name = re.sub(r"[\x00-\x1f\x7f]", "_", name).strip(" .")
    if not name or name in {".", ".."}:
        return "attachment"
    return name[:255]
