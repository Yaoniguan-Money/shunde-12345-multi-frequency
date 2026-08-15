"""Taxonomy API routes.

提供标准分类目录的查询接口：
- GET /taxonomies/active
- GET /taxonomies/{version_id}/tree
- GET /taxonomies/{version_id}/stats
- GET /taxonomies/{version_id}/nodes/{node_id}
- GET /taxonomies/{version_id}/resolve
- POST /taxonomies/seed
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.api.dependencies import TaxonomyServiceDependency
from backend.app.domain.taxonomy import (
    TaxonomyNode,
    TaxonomyTree,
    TaxonomyVersionInfo,
)
from backend.app.schemas.taxonomy import (
    CodeResolutionResponse,
    TaxonomyListResponse,
    TaxonomyNodeResponse,
    TaxonomySeedRequest,
    TaxonomySeedResponse,
    TaxonomyStatsResponse,
    TaxonomyTreeResponse,
    TaxonomyVersionResponse,
)

router = APIRouter(prefix="/taxonomies", tags=["taxonomy"])


def _node_to_response(node: TaxonomyNode) -> TaxonomyNodeResponse:
    assert node.taxonomy_version_id is not None, (
        "taxonomy_version_id must be set before serialization; loader-stage nodes "
        "cannot be returned from the API"
    )
    return TaxonomyNodeResponse(
        node_id=node.node_id,
        taxonomy_version_id=node.taxonomy_version_id,
        level=node.level.value,
        printed_code=node.printed_code,
        printed_name=node.printed_name,
        parent_node_id=node.parent_node_id,
        full_path=list(node.full_path),
        remark=node.remark,
        source_page=node.source_page,
        source_anomaly=node.source_anomaly,
        display_name=node.display_name,
        display_name_source=node.display_name_source.value,
    )


def _version_to_response(version: TaxonomyVersionInfo) -> TaxonomyVersionResponse:
    return TaxonomyVersionResponse(
        version_id=version.version_id,
        standard_name=version.standard_name,
        source_sha256=version.source_sha256,
        extracted_resource_sha256=version.extracted_resource_sha256,
        status=version.status.value,
        activated_at=version.activated_at,
        level_1_count=version.level_1_count,
        level_2_count=version.level_2_count,
        level_3_count=version.level_3_count,
        distinct_level_3_code_count=version.distinct_level_3_code_count,
        duplicate_printed_codes=list(version.duplicate_printed_codes),
        empty_level_3_name_count=version.empty_level_3_name_count,
    )


@router.get("/active", response_model=TaxonomyVersionResponse)
async def get_active_taxonomy(
    service: TaxonomyServiceDependency,
) -> TaxonomyVersionResponse:
    version = await service.get_active_version()
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no active taxonomy version; seed the DB44/T 2479-2024 appendix A first",
        )
    return _version_to_response(version)


@router.get("", response_model=TaxonomyListResponse)
async def list_taxonomies(
    service: TaxonomyServiceDependency,
) -> TaxonomyListResponse:
    versions = await service.list_versions()
    return TaxonomyListResponse(items=[_version_to_response(v) for v in versions])


@router.get("/{version_id}/tree", response_model=TaxonomyTreeResponse)
async def get_taxonomy_tree(
    version_id: UUID,
    service: TaxonomyServiceDependency,
) -> TaxonomyTreeResponse:
    from backend.app.domain.taxonomy import TaxonomyVersionId

    tree = await service.get_tree(TaxonomyVersionId(version_id))
    if tree is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"taxonomy version {version_id} not found",
        )
    assert isinstance(tree, TaxonomyTree)
    return TaxonomyTreeResponse(
        version=_version_to_response(tree.version),
        nodes=[_node_to_response(n) for n in tree.nodes],
    )


@router.get("/{version_id}/stats", response_model=TaxonomyStatsResponse)
async def get_taxonomy_stats(
    version_id: UUID,
    service: TaxonomyServiceDependency,
) -> TaxonomyStatsResponse:
    from backend.app.domain.taxonomy import TaxonomyVersionId

    stats = await service.get_stats(TaxonomyVersionId(version_id))
    if stats is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"taxonomy version {version_id} not found",
        )
    return TaxonomyStatsResponse(
        level_1_count=stats.level_1_count,
        level_2_count=stats.level_2_count,
        level_3_count=stats.level_3_count,
        distinct_level_3_code_count=stats.distinct_level_3_code_count,
        duplicate_printed_codes=[(code, count) for code, count in stats.duplicate_printed_codes],
        empty_level_3_name_count=stats.empty_level_3_name_count,
        duplicate_printed_code_paths=[
            (code, list(path)) for code, path in stats.duplicate_printed_code_paths
        ],
    )


@router.get("/{version_id}/resolve", response_model=CodeResolutionResponse)
async def resolve_printed_code(
    version_id: UUID,
    service: TaxonomyServiceDependency,
    printed_code: Annotated[str, Query(description="标准三级印刷代码，如 080508")],
    parent_printed_code: Annotated[
        str | None,
        Query(description="父二级印刷代码，用于消歧 090499 等重码"),
    ] = None,
) -> CodeResolutionResponse:
    from backend.app.domain.taxonomy import TaxonomyVersionId

    # 确认版本存在
    tree = await service.get_tree(TaxonomyVersionId(version_id))
    if tree is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"taxonomy version {version_id} not found",
        )
    assert isinstance(tree, TaxonomyTree)

    from backend.app.infrastructure.taxonomy.resolver import resolve_by_printed_code

    resolution = resolve_by_printed_code(tree.nodes, printed_code, parent_printed_code)
    return CodeResolutionResponse(
        printed_code=resolution.printed_code,
        ambiguous=resolution.ambiguous,
        resolved_node=_node_to_response(resolution.resolved_node)
        if resolution.resolved_node
        else None,
        candidates=[_node_to_response(c) for c in resolution.candidates],
    )


@router.post("/seed", response_model=TaxonomySeedResponse, status_code=status.HTTP_201_CREATED)
async def seed_taxonomy(
    request: TaxonomySeedRequest,
    service: TaxonomyServiceDependency,
) -> TaxonomySeedResponse:
    """从 CSV 创建 draft version 并可选激活。

    仅用于初始化；不接收政府工单数据。
    """
    version, activated, errors = await service.seed_from_csv(
        request.csv_path, activate=request.activate
    )
    return TaxonomySeedResponse(
        version=_version_to_response(version),
        activated=activated,
        validation_errors=errors,
    )
