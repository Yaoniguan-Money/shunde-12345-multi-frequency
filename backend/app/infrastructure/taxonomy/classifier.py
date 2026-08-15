"""标准分类器——确定性 source code 路径 + taxonomy-constrained 模型路径。

source code
  -> normalize
  -> taxonomy lookup
  -> hierarchy validation
  -> classification_node_id

无代码时：
  current event facts
  -> deterministic candidate narrowing
  -> bounded provider classification
  -> classification_node_id only
  -> taxonomy validator

模型输出不能直接携带自创中文类型。
最终存储的名称和父路径始终来自 taxonomy。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.app.domain.taxonomy import (
    ClassificationDecision,
    ClassificationOutcome,
    ClassificationSource,
    CodeResolution,
    TaxonomyNode,
    TaxonomyTree,
)

_CODE_PATTERN = re.compile(r"^[\dA-Za-z]{6}$")


def normalize_printed_code(raw: str) -> str:
    """规范化全角/半角和空白。"""
    cleaned = raw.strip()
    normalized = cleaned.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    return normalized.replace(" ", "").replace("\u3000", "")


def is_valid_code(code: str) -> bool:
    """验证代码长度与字符。"""
    return bool(_CODE_PATTERN.match(code))


@dataclass(frozen=True, slots=True)
class SourceCodeClassificationResult:
    outcome: ClassificationOutcome
    resolved_node: TaxonomyNode | None


def classify_by_source_code(
    raw_code: str | None,
    parent_printed_code: str | None,
    tree: TaxonomyTree,
) -> SourceCodeClassificationResult:
    """确定性 source code 分类路径。

    1. 规范化全角/半角和空白
    2. 验证代码长度与字符
    3. 在当前 active taxonomy 中查找
    4. 唯一命中则确定性绑定
    5. 090499 等歧义代码必须结合来源父级代码或完整路径
    6. 无法唯一定位时明确 ambiguous_source_code，不能调用 AI 随意选一条
    """
    if not raw_code:
        return SourceCodeClassificationResult(
            outcome=ClassificationOutcome(
                classification_node_id=None,
                candidate_node_ids=(),
                decision=ClassificationDecision.UNRESOLVED,
                confidence=0.0,
                evidence_refs=(),
                reason="no source code provided",
                provider_profile=None,
                taxonomy_version=tree.version.standard_name,
            ),
            resolved_node=None,
        )

    code = normalize_printed_code(raw_code)
    if not is_valid_code(code):
        return SourceCodeClassificationResult(
            outcome=ClassificationOutcome(
                classification_node_id=None,
                candidate_node_ids=(),
                decision=ClassificationDecision.UNRESOLVED,
                confidence=0.0,
                evidence_refs=(),
                reason=f"invalid code format: {raw_code}",
                provider_profile=None,
                taxonomy_version=tree.version.standard_name,
            ),
            resolved_node=None,
        )

    matching_nodes = tuple(
        node for node in tree.nodes if node.printed_code == code
    )

    if not matching_nodes:
        return SourceCodeClassificationResult(
            outcome=ClassificationOutcome(
                classification_node_id=None,
                candidate_node_ids=(),
                decision=ClassificationDecision.UNRESOLVED,
                confidence=0.0,
                evidence_refs=(),
                reason=f"code {code} not found in active taxonomy",
                provider_profile=None,
                taxonomy_version=tree.version.standard_name,
            ),
            resolved_node=None,
        )

    if len(matching_nodes) == 1:
        node = matching_nodes[0]
        return SourceCodeClassificationResult(
            outcome=ClassificationOutcome(
                classification_node_id=node.node_id,
                candidate_node_ids=(node.node_id,),
                decision=ClassificationDecision.RESOLVED,
                confidence=1.0,
                evidence_refs=(),
                reason=f"deterministic source_code match: {code}",
                provider_profile=None,
                taxonomy_version=tree.version.standard_name,
            ),
            resolved_node=node,
        )

    # 多条命中（如 090499），尝试用父代码缩小
    if parent_printed_code:
        parent_normalized = normalize_printed_code(parent_printed_code)
        narrowed = tuple(
            node
            for node in matching_nodes
            if node.parent_node_id
            and _node_matches_parent_code(node, tree, parent_normalized)
        )
        if len(narrowed) == 1:
            node = narrowed[0]
            return SourceCodeClassificationResult(
                outcome=ClassificationOutcome(
                    classification_node_id=node.node_id,
                    candidate_node_ids=(node.node_id,),
                    decision=ClassificationDecision.RESOLVED,
                    confidence=1.0,
                    evidence_refs=(),
                    reason=f"deterministic source_code match with parent {parent_normalized}: {code}",
                    provider_profile=None,
                    taxonomy_version=tree.version.standard_name,
                ),
                resolved_node=node,
            )

    candidates = tuple(node.node_id for node in matching_nodes)
    return SourceCodeClassificationResult(
        outcome=ClassificationOutcome(
            classification_node_id=None,
            candidate_node_ids=candidates,
            decision=ClassificationDecision.AMBIGUOUS,
            confidence=0.0,
            evidence_refs=(),
            reason=f"code {code} matches {len(matching_nodes)} nodes; provide parent code",
            provider_profile=None,
            taxonomy_version=tree.version.standard_name,
        ),
        resolved_node=None,
    )


def _node_matches_parent_code(
    node: TaxonomyNode, tree: TaxonomyTree, parent_code: str
) -> bool:
    """Check if node's parent has the given printed_code."""
    if node.parent_node_id is None:
        return False
    parent = tree.node_by_id.get(node.parent_node_id)
    return parent is not None and parent.printed_code == parent_code


@dataclass(frozen=True, slots=True)
class ModelClassificationResult:
    outcome: ClassificationOutcome
    resolved_node: TaxonomyNode | None


def classify_by_model(
    model_node_id: str | None,
    model_candidate_ids: list[str],
    model_confidence: float,
    model_decision: str,
    model_reason: str | None,
    model_evidence_refs: list[str],
    tree: TaxonomyTree,
    provider_profile: str | None,
) -> ModelClassificationResult:
    """Taxonomy-constrained 模型分类路径。

    模型输出不能直接携带自创中文类型。
    最终存储的名称和父路径始终来自 taxonomy。
    """
    node_by_id = tree.node_by_id

    valid_candidates = tuple(
        nid for nid in model_candidate_ids if nid in node_by_id
    )

    if model_node_id and model_node_id in node_by_id:
        node = node_by_id[model_node_id]
        return ModelClassificationResult(
            outcome=ClassificationOutcome(
                classification_node_id=node.node_id,
                candidate_node_ids=valid_candidates,
                decision=ClassificationDecision.RESOLVED,
                confidence=min(max(model_confidence, 0.0), 1.0),
                evidence_refs=tuple(model_evidence_refs),
                reason=model_reason,
                provider_profile=provider_profile,
                taxonomy_version=tree.version.standard_name,
            ),
            resolved_node=node,
        )

    if model_decision == ClassificationDecision.AMBIGUOUS.value and valid_candidates:
        return ModelClassificationResult(
            outcome=ClassificationOutcome(
                classification_node_id=None,
                candidate_node_ids=valid_candidates,
                decision=ClassificationDecision.AMBIGUOUS,
                confidence=min(max(model_confidence, 0.0), 1.0),
                evidence_refs=tuple(model_evidence_refs),
                reason=model_reason,
                provider_profile=provider_profile,
                taxonomy_version=tree.version.standard_name,
            ),
            resolved_node=None,
        )

    return ModelClassificationResult(
        outcome=ClassificationOutcome(
            classification_node_id=None,
            candidate_node_ids=valid_candidates,
            decision=ClassificationDecision.UNRESOLVED,
            confidence=0.0,
            evidence_refs=tuple(model_evidence_refs),
            reason=model_reason or "model classification unresolved",
            provider_profile=provider_profile,
            taxonomy_version=tree.version.standard_name,
        ),
        resolved_node=None,
    )
