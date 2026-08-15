"""Taxonomy 端口定义。

应用层依赖这些端口；基础设施层提供 SQLAlchemy adapter。
"""

from __future__ import annotations

from collections.abc import Sequence

from backend.app.domain.taxonomy import (
    ClassificationOutcome,
    CodeResolution,
    TaxonomyNode,
    TaxonomyNodeId,
    TaxonomyStats,
    TaxonomyTree,
    TaxonomyVersionId,
    TaxonomyVersionInfo,
)


class TaxonomyRepository:
    """Taxonomy 仓库端口。

    实现必须保证：
    - active version 全局唯一；
    - 激活校验失败时拒绝激活；
    - 按 printed_code 查询返回所有匹配（包括 090499 两条）；
    - 按 node_id 或完整父路径查询时唯一定位。
    """

    async def list_versions(self) -> Sequence[TaxonomyVersionInfo]:
        raise NotImplementedError

    async def get_version(self, version_id: TaxonomyVersionId) -> TaxonomyVersionInfo | None:
        raise NotImplementedError

    async def get_active_version(self) -> TaxonomyVersionInfo | None:
        raise NotImplementedError

    async def get_tree(self, version_id: TaxonomyVersionId) -> TaxonomyTree | None:
        raise NotImplementedError

    async def get_stats(self, version_id: TaxonomyVersionId) -> TaxonomyStats | None:
        raise NotImplementedError

    async def get_node(self, node_id: TaxonomyNodeId) -> TaxonomyNode | None:
        raise NotImplementedError

    async def resolve_by_printed_code(
        self, printed_code: str, parent_printed_code: str | None = None
    ) -> CodeResolution:
        raise NotImplementedError

    async def resolve_by_full_path(self, full_path: Sequence[str]) -> TaxonomyNode | None:
        raise NotImplementedError

    async def create_draft_version(
        self,
        standard_name: str,
        source_sha256: str,
        extracted_resource_sha256: str,
        nodes: Sequence[TaxonomyNode],
    ) -> TaxonomyVersionInfo:
        raise NotImplementedError

    async def activate_version(self, version_id: TaxonomyVersionId) -> TaxonomyVersionInfo:
        """激活前必须通过完整性校验；失败抛 TaxonomyValidationError。"""
        raise NotImplementedError

    async def retire_version(self, version_id: TaxonomyVersionId) -> TaxonomyVersionInfo:
        raise NotImplementedError


class ClassificationValidator:
    """分类输出 Validator 端口。

    检查 AI 或来源代码产生的分类结果是否符合 taxonomy 合同：
    - 节点存在且属于 active version；
    - 父路径完整；
    - 证据确实来自当前投诉；
    - 结果不是自由文本；
    - 置信和歧义状态符合合同。
    """

    async def validate(
        self,
        outcome: ClassificationOutcome,
        active_tree: TaxonomyTree,
    ) -> ClassificationOutcome:
        raise NotImplementedError
