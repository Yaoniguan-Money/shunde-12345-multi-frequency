from uuid import UUID

from pydantic import BaseModel


class AttachmentResponse(BaseModel):
    attachment_id: UUID
    reference: str
    original_filename: str
    size: int
    content_type: str
