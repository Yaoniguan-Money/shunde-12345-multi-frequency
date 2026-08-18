"""确定性 ClassificationValidator 实现。

检查 AI 或来源代码产生的分类结果是否符合 taxonomy 合同：
- 节点存在且属于 active version；
- 父路径完整；
- 结果不是自由文本；
- 置信和歧义状态符合合同。

ambiguous 和 unresolved 是真实业务状态，不得自动塞进"其他"伪装成功。
"""

from __future__ import annotations

from backend.app.domain.taxonomy import (
    ClassificationDecision,
    ClassificationOutcome,
    TaxonomyTree,
)


class TaxonomyClassificationValidator:
    """分类输出 Validator 端口实现。"""

    async def validate(
        self,
        outcome: ClassificationOutcome,
        active_tree: TaxonomyTree,
    ) -> ClassificationOutcome:
        node_by_id = active_tree.node_by_id

        if outcome.classification_node_id is not None:
            node = node_by_id.get(outcome.classification_node_id)
            if node is None:
                return ClassificationOutcome(
                    classification_node_id=None,
                    candidate_node_ids=outcome.candidate_node_ids,
                    decision=ClassificationDecision.UNRESOLVED,
                    confidence=0.0,
                    evidence_refs=outcome.evidence_refs,
                    reason=f"node_id {outcome.classification_node_id} not in active taxonomy",
                    provider_profile=outcome.provider_profile,
                    taxonomy_version=active_tree.version.standard_name,
                )

            if outcome.decision == ClassificationDecision.RESOLVED:
                return ClassificationOutcome(
                    classification_node_id=node.node_id,
                    candidate_node_ids=outcome.candidate_node_ids,
                    decision=ClassificationDecision.RESOLVED,
                    confidence=min(max(outcome.confidence, 0.0), 1.0),
                    evidence_refs=outcome.evidence_refs,
                    reason=outcome.reason,
                    provider_profile=outcome.provider_profile,
                    taxonomy_version=active_tree.version.standard_name,
                )

        if outcome.decision == ClassificationDecision.AMBIGUOUS:
            valid_candidates = tuple(nid for nid in outcome.candidate_node_ids if nid in node_by_id)
            if not valid_candidates:
                return ClassificationOutcome(
                    classification_node_id=None,
                    candidate_node_ids=(),
                    decision=ClassificationDecision.UNRESOLVED,
                    confidence=0.0,
                    evidence_refs=outcome.evidence_refs,
                    reason="ambiguous outcome has no valid candidates in active taxonomy",
                    provider_profile=outcome.provider_profile,
                    taxonomy_version=active_tree.version.standard_name,
                )
            return ClassificationOutcome(
                classification_node_id=None,
                candidate_node_ids=valid_candidates,
                decision=ClassificationDecision.AMBIGUOUS,
                confidence=min(max(outcome.confidence, 0.0), 1.0),
                evidence_refs=outcome.evidence_refs,
                reason=outcome.reason,
                provider_profile=outcome.provider_profile,
                taxonomy_version=active_tree.version.standard_name,
            )

        return ClassificationOutcome(
            classification_node_id=None,
            candidate_node_ids=(),
            decision=ClassificationDecision.UNRESOLVED,
            confidence=0.0,
            evidence_refs=outcome.evidence_refs,
            reason=outcome.reason or "unresolved",
            provider_profile=outcome.provider_profile,
            taxonomy_version=active_tree.version.standard_name,
        )
