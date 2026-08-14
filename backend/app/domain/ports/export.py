from typing import Protocol

from backend.app.domain.types import ExportArtifact, ExportRequest


class Exporter(Protocol):
    async def export(self, request: ExportRequest) -> ExportArtifact: ...
