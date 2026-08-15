import httpx
import pytest

from backend.app.api.dependencies import get_attachment_store
from backend.app.infrastructure.attachments import LocalAttachmentStore
from backend.app.main import create_app


@pytest.mark.asyncio
async def test_attachment_upload_download_is_bounded_and_filename_safe(tmp_path) -> None:
    store = LocalAttachmentStore(tmp_path / "runtime-attachments", max_bytes=8)
    app = create_app()
    app.dependency_overrides[get_attachment_store] = lambda: store
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await client.post(
            "/attachments",
            files={"file": ("../核查.txt", b"evidence", "text/plain")},
        )
        downloaded = await client.get(f"/attachments/{uploaded.json()['attachment_id']}")
        too_large = await client.post(
            "/attachments",
            files={"file": ("large.bin", b"123456789", "application/octet-stream")},
        )

    assert uploaded.status_code == 201
    assert uploaded.json()["original_filename"] == "核查.txt"
    assert uploaded.json()["size"] == 8
    assert "runtime-attachments" not in uploaded.text
    assert downloaded.status_code == 200
    assert downloaded.content == b"evidence"
    assert too_large.status_code == 413
