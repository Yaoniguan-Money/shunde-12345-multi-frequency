"""DB44/T 2479—2024 附录 A CSV 加载器与完整性校验。

本模块把 `docs/presentation-alignment-plan/reference/db44t2479-2024-appendix-a.csv`
转换为领域 TaxonomyNode 集合，并在激活前执行完整性校验。

校验规则来自 `docs/presentation-alignment-plan/01-DB44-TAXONOMY.md` §8：
- 一级节点数为 14；
- 二级节点数为 99；
- 三级记录数为 515；
- 不同三级印刷代码数为 514；
- 唯一重复代码恰好为 `090499` 两条；
- 所有节点父路径存在；
- 三个关键代码 `040201`、`080508`、`100401` 名称和路径完全匹配；
- 13 条空三级名称被保留并登记。

任何校验失败都必须拒绝激活，不能加载半份目录继续运行。
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Iterator, Sequence
from pathlib import Path

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
    TaxonomyNode,
    TaxonomyNodeId,
    TaxonomyStats,
    TaxonomyValidationError,
)

# CSV 列顺序
_CSV_COLUMNS = (
    "node_id",
    "level_1_code",
    "level_1_name",
    "level_2_code",
    "level_2_name",
    "level_3_code",
    "level_3_name",
    "remark",
    "source_pdf_page",
    "source_anomaly",
)


def _normalize_code(raw: str) -> str:
    """规范化全角/半角和空白。"""
    # 全角数字转半角
    fullwidth_map = str.maketrans("０１２３４５６７８９", "0123456789")
    return raw.translate(fullwidth_map).strip()


def _build_level_1_node(
    code: str,
    name: str,
    source_page: int | None,
) -> TaxonomyNode:
    node_id = TaxonomyNodeId(f"db44t2479-2024:{code}")
    return TaxonomyNode(
        node_id=node_id,
        taxonomy_version_id=None,  # 由仓库在持久化时填入
        level=TaxonomyLevel.LEVEL_1,
        printed_code=code,
        printed_name=name,
        parent_node_id=None,
        full_path=(code,),
        remark=None,
        source_page=source_page,
        source_anomaly=None,
        display_name=name,
        display_name_source=DisplayNameSource.PRINTED,
    )


def _build_level_2_node(
    level_1_code: str,
    level_1_name: str,
    level_2_code: str,
    level_2_name: str,
    source_page: int | None,
) -> TaxonomyNode:
    node_id = TaxonomyNodeId(f"db44t2479-2024:{level_2_code}")
    parent_node_id = TaxonomyNodeId(f"db44t2479-2024:{level_1_code}")
    return TaxonomyNode(
        node_id=node_id,
        taxonomy_version_id=None,
        level=TaxonomyLevel.LEVEL_2,
        printed_code=level_2_code,
        printed_name=level_2_name,
        parent_node_id=parent_node_id,
        full_path=(level_1_code, level_2_code),
        remark=None,
        source_page=source_page,
        source_anomaly=None,
        display_name=level_2_name,
        display_name_source=DisplayNameSource.PRINTED,
    )


def _build_level_3_node(
    node_id: str,
    level_1_code: str,
    level_1_name: str,
    level_2_code: str,
    level_2_name: str,
    level_3_code: str,
    level_3_name: str | None,
    remark: str | None,
    source_page: int | None,
    source_anomaly: str | None,
) -> TaxonomyNode:
    # display_name 继承规则：printed_name 非空用 printed，否则继承 level_2_name，再否则 level_1_name
    if level_3_name:
        display_name = level_3_name
        display_name_source = DisplayNameSource.PRINTED
    elif level_2_name:
        display_name = level_2_name
        display_name_source = DisplayNameSource.LEVEL_2_INHERITED
    else:
        display_name = level_1_name
        display_name_source = DisplayNameSource.LEVEL_1_INHERITED

    return TaxonomyNode(
        node_id=TaxonomyNodeId(node_id),
        taxonomy_version_id=None,
        level=TaxonomyLevel.LEVEL_3,
        printed_code=level_3_code,
        printed_name=level_3_name or None,
        parent_node_id=TaxonomyNodeId(f"db44t2479-2024:{level_2_code}"),
        full_path=(level_1_code, level_2_code, level_3_code),
        remark=remark,
        source_page=source_page,
        source_anomaly=source_anomaly,
        display_name=display_name,
        display_name_source=display_name_source,
    )


def load_appendix_a(csv_path: Path) -> tuple[list[TaxonomyNode], TaxonomyStats]:
    """从 CSV 加载全部节点并计算统计。

    返回 (nodes, stats)。nodes 包含一级、二级、三级节点，去重后按 level 升序、code 升序排列。
    不执行完整性校验；调用方应调用 `validate_integrity` 校验后才允许激活。
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"附录 A CSV 不存在: {csv_path}")

    level_1_nodes: dict[str, TaxonomyNode] = {}
    level_2_nodes: dict[str, TaxonomyNode] = {}
    level_3_nodes: list[TaxonomyNode] = []

    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        _validate_csv_header(reader.fieldnames)
        for row in reader:
            level_1_code = _normalize_code(row["level_1_code"])
            level_1_name = row["level_1_name"].strip()
            level_2_code = _normalize_code(row["level_2_code"])
            level_2_name = row["level_2_name"].strip()
            level_3_code = _normalize_code(row["level_3_code"])
            level_3_name_raw = row["level_3_name"].strip()
            level_3_name = level_3_name_raw if level_3_name_raw else None
            remark = row["remark"].strip() or None
            source_page_raw = row["source_pdf_page"].strip()
            source_page = int(source_page_raw) if source_page_raw else None
            source_anomaly = row["source_anomaly"].strip() or None

            if level_1_code not in level_1_nodes:
                level_1_nodes[level_1_code] = _build_level_1_node(
                    level_1_code, level_1_name, source_page
                )
            if level_2_code not in level_2_nodes:
                level_2_nodes[level_2_code] = _build_level_2_node(
                    level_1_code,
                    level_1_name,
                    level_2_code,
                    level_2_name,
                    source_page,
                )
            level_3_nodes.append(
                _build_level_3_node(
                    row["node_id"].strip(),
                    level_1_code,
                    level_1_name,
                    level_2_code,
                    level_2_name,
                    level_3_code,
                    level_3_name,
                    remark,
                    source_page,
                    source_anomaly,
                )
            )

    nodes = list(level_1_nodes.values()) + list(level_2_nodes.values()) + level_3_nodes
    stats = _compute_stats(nodes, level_3_nodes)
    return nodes, stats


def _validate_csv_header(fieldnames: Sequence[str] | None) -> None:
    if fieldnames is None:
        raise TaxonomyValidationError(("CSV 缺少表头",))
    missing = [col for col in _CSV_COLUMNS if col not in fieldnames]
    if missing:
        raise TaxonomyValidationError((f"CSV 缺少列: {', '.join(missing)}",))


def _compute_stats(
    all_nodes: list[TaxonomyNode], level_3_nodes: list[TaxonomyNode]
) -> TaxonomyStats:
    level_1_count = sum(1 for n in all_nodes if n.level == TaxonomyLevel.LEVEL_1)
    level_2_count = sum(1 for n in all_nodes if n.level == TaxonomyLevel.LEVEL_2)
    level_3_count = len(level_3_nodes)

    code_counter: Counter[str] = Counter(n.printed_code for n in level_3_nodes)
    distinct_level_3_code_count = len(code_counter)
    duplicate_codes = tuple((code, count) for code, count in code_counter.items() if count > 1)
    duplicate_code_paths: list[tuple[str, tuple[str, ...]]] = []
    for code, _count in duplicate_codes:
        for node in level_3_nodes:
            if node.printed_code == code:
                duplicate_code_paths.append((code, node.full_path))

    empty_level_3_name_count = sum(1 for n in level_3_nodes if n.printed_name is None)

    return TaxonomyStats(
        level_1_count=level_1_count,
        level_2_count=level_2_count,
        level_3_count=level_3_count,
        distinct_level_3_code_count=distinct_level_3_code_count,
        duplicate_printed_codes=duplicate_codes,
        empty_level_3_name_count=empty_level_3_name_count,
        duplicate_printed_code_paths=tuple(duplicate_code_paths),
    )


def validate_integrity(nodes: list[TaxonomyNode], stats: TaxonomyStats) -> None:
    """执行附录 A 完整性校验。

    任何一项失败都抛 TaxonomyValidationError，拒绝激活。
    """
    errors: list[str] = []

    if stats.level_1_count != EXPECTED_LEVEL_1_COUNT:
        errors.append(f"一级节点数 {stats.level_1_count} != {EXPECTED_LEVEL_1_COUNT}")
    if stats.level_2_count != EXPECTED_LEVEL_2_COUNT:
        errors.append(f"二级节点数 {stats.level_2_count} != {EXPECTED_LEVEL_2_COUNT}")
    if stats.level_3_count != EXPECTED_LEVEL_3_COUNT:
        errors.append(f"三级记录数 {stats.level_3_count} != {EXPECTED_LEVEL_3_COUNT}")
    if stats.distinct_level_3_code_count != EXPECTED_DISTINCT_LEVEL_3_CODE_COUNT:
        errors.append(
            f"不同三级印刷代码数 {stats.distinct_level_3_code_count} "
            f"!= {EXPECTED_DISTINCT_LEVEL_3_CODE_COUNT}"
        )

    # 唯一重复代码恰好为 090499 两条
    duplicate_codes = stats.duplicate_printed_codes
    if len(duplicate_codes) != 1:
        errors.append(f"重复代码数量 {len(duplicate_codes)} != 1; 重复代码: {duplicate_codes}")
    elif duplicate_codes[0][0] != EXPECTED_DUPLICATE_PRINTED_CODE:
        errors.append(f"重复代码 {duplicate_codes[0][0]} != {EXPECTED_DUPLICATE_PRINTED_CODE}")
    elif duplicate_codes[0][1] != 2:
        errors.append(f"090499 重复条数 {duplicate_codes[0][1]} != 2")
    else:
        # 校验两条路径分别是 0904 和 0905
        paths = {tuple(path) for _code, path in stats.duplicate_printed_code_paths}
        if DUPLICATE_090499_PATH_A not in paths:
            errors.append(f"缺少 090499 路径 {DUPLICATE_090499_PATH_A}")
        if DUPLICATE_090499_PATH_B not in paths:
            errors.append(f"缺少 090499 路径 {DUPLICATE_090499_PATH_B}")

    if stats.empty_level_3_name_count != EXPECTED_EMPTY_LEVEL_3_NAME_COUNT:
        errors.append(
            f"空三级名称记录数 {stats.empty_level_3_name_count} "
            f"!= {EXPECTED_EMPTY_LEVEL_3_NAME_COUNT}"
        )

    # 所有节点父路径存在
    node_ids = {n.node_id for n in nodes}
    for node in nodes:
        if node.parent_node_id is not None and node.parent_node_id not in node_ids:
            errors.append(f"节点 {node.node_id} 的父节点 {node.parent_node_id} 不存在")

    # 关键代码名称和路径校验
    _validate_key_code(nodes, KEY_CODE_040201_PATH, KEY_CODE_040201_NAME, errors)
    _validate_key_code(nodes, KEY_CODE_080508_PATH, KEY_CODE_080508_NAME, errors)
    _validate_key_code(nodes, KEY_CODE_100401_PATH, KEY_CODE_100401_NAME, errors)

    if errors:
        raise TaxonomyValidationError(tuple(errors))


def _validate_key_code(
    nodes: list[TaxonomyNode],
    expected_path: tuple[str, ...],
    expected_name: str,
    errors: list[str],
) -> None:
    found = None
    for node in nodes:
        if node.full_path == expected_path:
            found = node
            break
    if found is None:
        errors.append(f"关键代码 {expected_path} 不存在")
        return
    if found.printed_name != expected_name:
        errors.append(f"关键代码 {expected_path} 名称 '{found.printed_name}' != '{expected_name}'")


def iter_level_3_nodes(nodes: Sequence[TaxonomyNode]) -> Iterator[TaxonomyNode]:
    for node in nodes:
        if node.level == TaxonomyLevel.LEVEL_3:
            yield node
