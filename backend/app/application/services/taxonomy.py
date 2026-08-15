"""Taxonomy application service.

编排 TaxonomyRepository 和 CSV loader，提供 seed/activate/tree/resolve 等用例。
"""

from __future__ import annotations

from pathlib import Path

from backend.app.domain.ports.taxonomy import TaxonomyRepository
from backend.app.domain.taxonomy import (
    EXTRACTED_RESOURCE_SHA256,
    SOURCE_PDF_SHA256,
    STANDARD_NAME,
    CodeResolution,
    TaxonomyNode,
    TaxonomyStats,
    TaxonomyTree,
    TaxonomyValidationError,
    TaxonomyVersionId,
    TaxonomyVersionInfo,
)
from backend.app.infrastructure.taxonomy.loader import load_appendix_a


class TaxonomyService:
    def __init__(self, repository: TaxonomyRepository) -> None:
        self._repository = repository

    async def seed_from_csv(
        self,
        csv_path: str,
        *,
        activate: bool = True,
    ) -> tuple[TaxonomyVersionInfo, bool, list[str] | None]:
        """从 CSV 创建 draft version，可选激活。

        返回 (version_info, activated, validation_errors)。
        激活失败时返回 (version_info, False, errors)，不抛异常。
        """
        path = Path(csv_path)
        nodes, _stats = load_appendix_a(path)

        version_info = await self._repository.create_draft_version(
            standard_name=STANDARD_NAME,
            source_sha256=SOURCE_PDF_SHA256,
            extracted_resource_sha256=EXTRACTED_RESOURCE_SHA256,
            nodes=nodes,
        )

        if not activate:
            return version_info, False, None

        try:
            activated_version = await self._repository.activate_version(
                TaxonomyVersionId(version_info.version_id)
            )
            return activated_version, True, None
        except TaxonomyValidationError as exc:
            return version_info, False, list(exc.errors)

    async def get_active_version(self) -> TaxonomyVersionInfo | None:
        return await self._repository.get_active_version()

    async def list_versions(self) -> list[TaxonomyVersionInfo]:
        return list(await self._repository.list_versions())

    async def get_tree(self, version_id: TaxonomyVersionId) -> TaxonomyTree | None:
        return await self._repository.get_tree(version_id)

    async def get_stats(self, version_id: TaxonomyVersionId) -> TaxonomyStats | None:
        return await self._repository.get_stats(version_id)

    async def resolve_by_printed_code(
        self,
        printed_code: str,
        parent_printed_code: str | None = None,
    ) -> CodeResolution:
        return await self._repository.resolve_by_printed_code(printed_code, parent_printed_code)

    async def resolve_by_full_path(self, full_path: list[str]) -> TaxonomyNode | None:
        return await self._repository.resolve_by_full_path(full_path)
