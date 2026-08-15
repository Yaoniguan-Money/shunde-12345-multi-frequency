"""DB44/T 2479—2024 附录 A 标准分类领域模型。

本模块定义 taxonomy 的纯领域类型，不依赖 SQLAlchemy、FastAPI 或具体模型厂商。
ORM 模型位于 `backend.app.infrastructure.db.models.taxonomy`。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import NewType
from uuid import UUID

TaxonomyVersionId = NewType("TaxonomyVersionId", UUID)
TaxonomyNodeId = NewType("TaxonomyNodeId", str)


class TaxonomyLevel(StrEnum):
    LEVEL_1 = "1"
    LEVEL_2 = "2"
    LEVEL_3 = "3"


class TaxonomyVersionStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class ClassificationSource(StrEnum):
    SOURCE_CODE = "source_code"
    MODEL = "model"
    HUMAN = "human"


class ClassificationDecision(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"
    HUMAN_CORRECTED = "human_corrected"


class DisplayNameSource(StrEnum):
    PRINTED = "printed"
    LEVEL_2_INHERITED = "level_2_inherited"
    LEVEL_1_INHERITED = "level_1_inherited"


@dataclass(frozen=True, slots=True)
class TaxonomyVersionInfo:
    """Taxonomy 版本元信息（不含节点）。"""

    version_id: TaxonomyVersionId
    standard_name: str
    source_sha256: str
    extracted_resource_sha256: str
    status: TaxonomyVersionStatus
    activated_at: datetime | None
    level_1_count: int
    level_2_count: int
    level_3_count: int
    distinct_level_3_code_count: int
    duplicate_printed_codes: tuple[str, ...]
    empty_level_3_name_count: int


@dataclass(frozen=True, slots=True)
class TaxonomyNode:
    """Taxonomy 节点。

    `printed_name` 可为 None（附录 A 有 13 条空三级名称，保真不伪造）。
    `full_path` 是从一级到本节点的完整路径，用于区分 `090499` 重码。
    `taxonomy_version_id` 在 loader 阶段为 None，由 repository 在持久化时填入。
    """

    node_id: TaxonomyNodeId
    taxonomy_version_id: TaxonomyVersionId | None
    level: TaxonomyLevel
    printed_code: str
    printed_name: str | None
    parent_node_id: TaxonomyNodeId | None
    full_path: tuple[str, ...]
    remark: str | None
    source_page: int | None
    source_anomaly: str | None
    display_name: str
    display_name_source: DisplayNameSource


@dataclass(frozen=True, slots=True)
class TaxonomyTree:
    """完整 taxonomy 树（active version）。"""

    version: TaxonomyVersionInfo
    nodes: tuple[TaxonomyNode, ...]

    @property
    def node_by_id(self) -> dict[TaxonomyNodeId, TaxonomyNode]:
        return {node.node_id: node for node in self.nodes}


@dataclass(frozen=True, slots=True)
class TaxonomyStats:
    """Taxonomy 完整性统计。"""

    level_1_count: int
    level_2_count: int
    level_3_count: int
    distinct_level_3_code_count: int
    duplicate_printed_codes: tuple[tuple[str, int], ...]
    empty_level_3_name_count: int
    duplicate_printed_code_paths: tuple[tuple[str, tuple[str, ...]], ...]


@dataclass(frozen=True, slots=True)
class CodeResolution:
    """按 printed_code 解析的结果。

    `090499` 等重码返回 `ambiguous=True` 并列出所有候选节点；
    调用方必须结合来源父级代码或完整路径选择唯一节点。
    """

    printed_code: str
    ambiguous: bool
    resolved_node: TaxonomyNode | None
    candidates: tuple[TaxonomyNode, ...]


@dataclass(frozen=True, slots=True)
class ClassificationOutcome:
    """标准分类输出合同。"""

    classification_node_id: TaxonomyNodeId
    candidate_node_ids: tuple[TaxonomyNodeId, ...]
    decision: ClassificationDecision
    confidence: float
    evidence_refs: tuple[str, ...]
    reason: str | None
    provider_profile: str | None
    taxonomy_version: str


@dataclass(frozen=True, slots=True)
class TaxonomyValidationError(Exception):
    """Taxonomy 激活校验失败。

    任何校验失败都必须拒绝激活，不能加载半份目录继续运行。
    """

    errors: tuple[str, ...] = field(default_factory=tuple)

    def __str__(self) -> str:
        joined = "; ".join(self.errors)
        return f"TaxonomyValidationError: {joined}"


# 附录 A 锁定常量（来自 reference/APPENDIX-A-VALIDATION.md）
STANDARD_NAME = "DB44/T 2479—2024 附录 A"
SOURCE_PDF_SHA256 = "7EE0C304308C9B65DD626D7DF2442CEDE4A89615B40C193EDDC5E9AF2A7535FC"
EXTRACTED_RESOURCE_SHA256 = "48D6C7B12C12BFBE29B65498B6F9D7166706433A95DF81B7269142895B4ADF97"

EXPECTED_LEVEL_1_COUNT = 14
EXPECTED_LEVEL_2_COUNT = 99
EXPECTED_LEVEL_3_COUNT = 515
EXPECTED_DISTINCT_LEVEL_3_CODE_COUNT = 514
EXPECTED_DUPLICATE_PRINTED_CODE = "090499"
EXPECTED_EMPTY_LEVEL_3_NAME_COUNT = 13

# 关键验收代码（来自 01-DB44-TAXONOMY.md §6）
KEY_CODE_040201_PATH = ("04", "0402", "040201")
KEY_CODE_040201_NAME = "噪声污染"
KEY_CODE_080508_PATH = ("08", "0805", "080508")
KEY_CODE_080508_NAME = "拖欠、克扣工资"
KEY_CODE_100401_PATH = ("10", "1004", "100401")
KEY_CODE_100401_NAME = "质量监督"

# 090499 两条不同父路径
DUPLICATE_090499_PATH_A = ("09", "0904", "090499")  # 民政社区/生活服务/其他生活服务
DUPLICATE_090499_PATH_B = ("09", "0905", "090499")  # 民政社区/民族宗教/其他民族宗教
