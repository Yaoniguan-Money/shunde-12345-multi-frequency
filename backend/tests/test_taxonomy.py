"""WP1 测试：附录 A 目录加载、完整性校验和代码解析。

覆盖 09-TESTS-ACCEPTANCE.md §2 的纯函数测试项：
- 14 个一级、99 个二级、515 条三级记录；
- 不同三级印刷代码 514 个；
- 唯一重码 090499 恰好两条不同父路径；
- 13 条空三级名称保真及显示名继承；
- 040201、080508、100401 精确名称和父路径；
- 按 source code 确定性绑定；
- 仅传 090499 返回歧义，不默认第一条；
- AI 输出自由文本或不存在 node_id 时被 Validator 拒绝（由
  ClassificationValidator 覆盖，本文件测试 resolver 行为）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.domain.taxonomy import (
    DUPLICATE_090499_PATH_A,
    DUPLICATE_090499_PATH_B,
    EXPECTED_DISTINCT_LEVEL_3_CODE_COUNT,
    EXPECTED_DUPLICATE_PRINTED_CODE,
    EXPECTED_EMPTY_LEVEL_3_NAME_COUNT,
    EXPECTED_LEVEL_1_COUNT,
    EXPECTED_LEVEL_2_COUNT,
    EXPECTED_LEVEL_3_COUNT,
    KEY_CODE_040201_NAME,
    KEY_CODE_040201_PATH,
    KEY_CODE_080508_NAME,
    KEY_CODE_080508_PATH,
    KEY_CODE_100401_NAME,
    KEY_CODE_100401_PATH,
    DisplayNameSource,
    TaxonomyLevel,
    TaxonomyValidationError,
)
from backend.app.infrastructure.taxonomy.loader import (
    load_appendix_a,
    validate_integrity,
)
from backend.app.infrastructure.taxonomy.resolver import (
    resolve_by_full_path,
    resolve_by_printed_code,
)

CSV_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "docs"
    / "presentation-alignment-plan"
    / "reference"
    / "db44t2479-2024-appendix-a.csv"
)


@pytest.fixture(scope="module")
def loaded() -> tuple[list, object]:
    nodes, stats = load_appendix_a(CSV_PATH)
    return nodes, stats


def test_csv_exists() -> None:
    assert CSV_PATH.exists(), f"附录 A CSV 不存在: {CSV_PATH}"


def test_taxonomy_counts(loaded: tuple[list, object]) -> None:
    nodes, stats = loaded
    assert stats.level_1_count == EXPECTED_LEVEL_1_COUNT
    assert stats.level_2_count == EXPECTED_LEVEL_2_COUNT
    assert stats.level_3_count == EXPECTED_LEVEL_3_COUNT
    assert stats.distinct_level_3_code_count == EXPECTED_DISTINCT_LEVEL_3_CODE_COUNT


def test_total_node_count(loaded: tuple[list, object]) -> None:
    nodes, _stats = loaded
    # 14 + 99 + 515 = 628
    assert len(nodes) == EXPECTED_LEVEL_1_COUNT + EXPECTED_LEVEL_2_COUNT + EXPECTED_LEVEL_3_COUNT


def test_duplicate_printed_code_is_090499_with_two_paths(loaded: tuple[list, object]) -> None:
    _nodes, stats = loaded
    duplicate_codes = stats.duplicate_printed_codes
    assert len(duplicate_codes) == 1
    code, count = duplicate_codes[0]
    assert code == EXPECTED_DUPLICATE_PRINTED_CODE
    assert count == 2

    paths = {tuple(path) for _code, path in stats.duplicate_printed_code_paths}
    assert DUPLICATE_090499_PATH_A in paths
    assert DUPLICATE_090499_PATH_B in paths


def test_empty_level_3_name_count(loaded: tuple[list, object]) -> None:
    _nodes, stats = loaded
    assert stats.empty_level_3_name_count == EXPECTED_EMPTY_LEVEL_3_NAME_COUNT


def test_empty_level_3_names_are_preserved_not_fabricated(loaded: tuple[list, object]) -> None:
    nodes, _stats = loaded
    level_3 = [n for n in nodes if n.level == TaxonomyLevel.LEVEL_3]
    empty_nodes = [n for n in level_3 if n.printed_name is None]
    assert len(empty_nodes) == EXPECTED_EMPTY_LEVEL_3_NAME_COUNT

    # 空名称节点必须有继承 display_name 和正确的 source
    for node in empty_nodes:
        assert node.display_name  # 非空
        assert node.display_name_source in (
            DisplayNameSource.LEVEL_2_INHERITED,
            DisplayNameSource.LEVEL_1_INHERITED,
        )


def test_integrity_validation_passes(loaded: tuple[list, object]) -> None:
    nodes, stats = loaded
    # 不抛异常即通过
    validate_integrity(nodes, stats)


def test_key_codes_have_correct_names_and_paths(loaded: tuple[list, object]) -> None:
    nodes, _stats = loaded
    for path, name in (
        (KEY_CODE_040201_PATH, KEY_CODE_040201_NAME),
        (KEY_CODE_080508_PATH, KEY_CODE_080508_NAME),
        (KEY_CODE_100401_PATH, KEY_CODE_100401_NAME),
    ):
        node = resolve_by_full_path(nodes, path)
        assert node is not None, f"关键代码 {path} 未找到"
        assert node.printed_name == name, f"{path}: {node.printed_name!r} != {name!r}"
        assert node.level == TaxonomyLevel.LEVEL_3


def test_resolve_by_printed_code_unique(loaded: tuple[list, object]) -> None:
    nodes, _stats = loaded
    # 080508 唯一命中
    resolution = resolve_by_printed_code(nodes, "080508")
    assert not resolution.ambiguous
    assert resolution.resolved_node is not None
    assert resolution.resolved_node.printed_code == "080508"
    assert resolution.resolved_node.printed_name == "拖欠、克扣工资"


def test_resolve_by_printed_code_090499_ambiguous(loaded: tuple[list, object]) -> None:
    nodes, _stats = loaded
    # 仅传 090499 返回歧义，不默认第一条
    resolution = resolve_by_printed_code(nodes, "090499")
    assert resolution.ambiguous
    assert resolution.resolved_node is None
    assert len(resolution.candidates) == 2
    paths = {tuple(c.full_path) for c in resolution.candidates}
    assert DUPLICATE_090499_PATH_A in paths
    assert DUPLICATE_090499_PATH_B in paths


def test_resolve_by_printed_code_090499_disambiguated_by_parent(
    loaded: tuple[list, object],
) -> None:
    nodes, _stats = loaded
    # 传 parent_printed_code=0904 应唯一解析到"其他生活服务"
    resolution = resolve_by_printed_code(nodes, "090499", parent_printed_code="0904")
    assert not resolution.ambiguous
    assert resolution.resolved_node is not None
    assert resolution.resolved_node.printed_name == "其他生活服务"

    # 传 parent_printed_code=0905 应唯一解析到"其他民族宗教"
    resolution = resolve_by_printed_code(nodes, "090499", parent_printed_code="0905")
    assert not resolution.ambiguous
    assert resolution.resolved_node is not None
    assert resolution.resolved_node.printed_name == "其他民族宗教"


def test_resolve_by_printed_code_not_found(loaded: tuple[list, object]) -> None:
    nodes, _stats = loaded
    resolution = resolve_by_printed_code(nodes, "999999")
    assert not resolution.ambiguous
    assert resolution.resolved_node is None
    assert resolution.candidates == ()


def test_resolve_by_full_path(loaded: tuple[list, object]) -> None:
    nodes, _stats = loaded
    node = resolve_by_full_path(nodes, ("08", "0805", "080508"))
    assert node is not None
    assert node.printed_code == "080508"

    node = resolve_by_full_path(nodes, ("09", "0904", "090499"))
    assert node is not None
    assert node.printed_name == "其他生活服务"

    node = resolve_by_full_path(nodes, ("09", "0905", "090499"))
    assert node is not None
    assert node.printed_name == "其他民族宗教"


def test_level_1_node_ids_are_distinct_from_level_2(loaded: tuple[list, object]) -> None:
    nodes, _stats = loaded
    level_1 = [n for n in nodes if n.level == TaxonomyLevel.LEVEL_1]
    level_2 = [n for n in nodes if n.level == TaxonomyLevel.LEVEL_2]
    level_1_ids = {n.node_id for n in level_1}
    level_2_ids = {n.node_id for n in level_2}
    # 090499 两条的 node_id 不同
    assert not level_1_ids.intersection(level_2_ids)


def test_integrity_validation_rejects_wrong_counts() -> None:
    """模拟计数错误应被校验拒绝。"""
    from backend.app.domain.taxonomy import TaxonomyStats

    fake_stats = TaxonomyStats(
        level_1_count=13,  # 错误，应为 14
        level_2_count=99,
        level_3_count=515,
        distinct_level_3_code_count=514,
        duplicate_printed_codes=(("090499", 2),),
        empty_level_3_name_count=13,
        duplicate_printed_code_paths=(
            ("090499", DUPLICATE_090499_PATH_A),
            ("090499", DUPLICATE_090499_PATH_B),
        ),
    )
    with pytest.raises(TaxonomyValidationError):
        validate_integrity([], fake_stats)


def test_integrity_validation_rejects_missing_duplicate_path() -> None:
    """090499 缺少一条路径应被拒绝。"""
    from backend.app.domain.taxonomy import TaxonomyStats

    fake_stats = TaxonomyStats(
        level_1_count=14,
        level_2_count=99,
        level_3_count=515,
        distinct_level_3_code_count=514,
        duplicate_printed_codes=(("090499", 2),),
        empty_level_3_name_count=13,
        duplicate_printed_code_paths=(("090499", DUPLICATE_090499_PATH_A),),  # 只有一条
    )
    with pytest.raises(TaxonomyValidationError) as exc_info:
        validate_integrity([], fake_stats)
    assert "0905" in " ".join(exc_info.value.errors) or "090499" in " ".join(exc_info.value.errors)
