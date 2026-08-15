"""Taxonomy 代码/路径解析器。

纯函数，操作内存中的节点集合。DB repository 可委托给这些函数或直接查询 DB。

解析规则（来自 01-DB44-TAXONOMY.md §5）：
- 来源已带代码时，规范化 -> 验证 -> 在 active taxonomy 中查找；
- 唯一命中则确定性绑定 classification_node_id；
- 090499 等歧义代码必须结合来源父级代码或完整路径；
- 无法唯一定位时明确 ambiguous_source_code，不能调用 AI 随意选一条。
"""

from __future__ import annotations

from collections.abc import Sequence

from backend.app.domain.taxonomy import (
    CodeResolution,
    TaxonomyNode,
)


def resolve_by_printed_code(
    nodes: Sequence[TaxonomyNode],
    printed_code: str,
    parent_printed_code: str | None = None,
) -> CodeResolution:
    """按 printed_code 解析节点。

    - 唯一命中：返回 resolved_node，ambiguous=False；
    - 多条命中且 parent_printed_code 给定：尝试用父代码缩小到唯一，成功则 resolved，否则 ambiguous；
    - 多条命中且无父代码：返回 ambiguous=True 和所有候选；
    - 无命中：返回 resolved_node=None, ambiguous=False, candidates=()。
    """
    matches = [n for n in nodes if n.printed_code == printed_code]

    if not matches:
        return CodeResolution(
            printed_code=printed_code,
            ambiguous=False,
            resolved_node=None,
            candidates=(),
        )

    if len(matches) == 1:
        return CodeResolution(
            printed_code=printed_code,
            ambiguous=False,
            resolved_node=matches[0],
            candidates=tuple(matches),
        )

    # 多条命中（如 090499）
    if parent_printed_code is not None:
        narrowed = [n for n in matches if _parent_code(n) == parent_printed_code]
        if len(narrowed) == 1:
            return CodeResolution(
                printed_code=printed_code,
                ambiguous=False,
                resolved_node=narrowed[0],
                candidates=tuple(matches),
            )
        # 父代码也歧义或无匹配，保持 ambiguous
        return CodeResolution(
            printed_code=printed_code,
            ambiguous=True,
            resolved_node=None,
            candidates=tuple(narrowed) if narrowed else tuple(matches),
        )

    return CodeResolution(
        printed_code=printed_code,
        ambiguous=True,
        resolved_node=None,
        candidates=tuple(matches),
    )


def resolve_by_full_path(
    nodes: Sequence[TaxonomyNode],
    full_path: Sequence[str],
) -> TaxonomyNode | None:
    """按完整父路径唯一定位节点。

    full_path 是从一级到目标节点的代码元组，如 ("09", "0904", "090499")。
    """
    target = tuple(full_path)
    for node in nodes:
        if tuple(node.full_path) == target:
            return node
    return None


def _parent_code(node: TaxonomyNode) -> str | None:
    """返回节点的父印刷代码（full_path 倒数第二个元素）。"""
    if len(node.full_path) < 2:
        return None
    return node.full_path[-2]
