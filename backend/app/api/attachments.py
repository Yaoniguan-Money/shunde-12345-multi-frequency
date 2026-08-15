from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from backend.app.api.dependencies import AttachmentStoreDependency
from backend.app.schemas.attachments import AttachmentResponse

router = APIRouter(tags=["attachments"])


@router.post("/attachments", response_model=AttachmentResponse, status_code=201)
async def upload_attachment(
    store: AttachmentStoreDependency, file: Annotated[UploadFile, File()]
) -> AttachmentResponse:
    async def chunks() -> AsyncIterator[bytes]:
        while chunk := await file.read(1024 * 1024):
            yield chunk

    try:
        metadata = await store.save(
            file.filename or "attachment", file.content_type or "application/octet-stream", chunks()
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(error)
        ) from error
    finally:
        await file.close()
    return AttachmentResponse(
        attachment_id=metadata.attachment_id,
        reference=metadata.reference,
        original_filename=metadata.original_filename,
        size=metadata.size,
        content_type=metadata.content_type,
    )


@router.get("/attachments/{attachment_id}")
async def download_attachment(
    attachment_id: UUID, store: AttachmentStoreDependency
) -> FileResponse:
    stored = await store.get(attachment_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="attachment not found")
    return FileResponse(
        stored.path,
        media_type=stored.metadata.content_type,
        filename=stored.metadata.original_filename,
    )
