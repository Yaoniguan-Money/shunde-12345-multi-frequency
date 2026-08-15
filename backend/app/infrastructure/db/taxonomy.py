"""SQLAlchemy adapter for TaxonomyRepository。

实现 `backend.app.domain.ports.taxonomy.TaxonomyRepository`。
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.domain.ports.taxonomy import TaxonomyRepository
from backend.app.domain.taxonomy import (
    CodeResolution,
    DisplayNameSource,
    TaxonomyLevel,
    TaxonomyNode,
    TaxonomyNodeId,
    TaxonomyStats,
    TaxonomyTree,
    TaxonomyValidationError,
    TaxonomyVersionId,
    TaxonomyVersionInfo,
    TaxonomyVersionStatus,
)
from backend.app.infrastructure.db.models.taxonomy import (
    TaxonomyNode as TaxonomyNodeORM,
)
from backend.app.infrastructure.db.models.taxonomy import (
    TaxonomyVersion as TaxonomyVersionORM,
)
from backend.app.infrastructure.taxonomy.loader import validate_integrity


class SQLAlchemyTaxonomyRepository(TaxonomyRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_versions(self) -> list[TaxonomyVersionInfo]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(TaxonomyVersionORM).order_by(TaxonomyVersionORM.created_at.desc())
            )
            return [self._to_version_info(v) for v in result.scalars().all()]

    async def get_version(self, version_id: TaxonomyVersionId) -> TaxonomyVersionInfo | None:
        async with self._session_factory() as session:
            orm = await session.get(TaxonomyVersionORM, version_id)
            return self._to_version_info(orm) if orm else None

    async def get_active_version(self) -> TaxonomyVersionInfo | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(TaxonomyVersionORM).where(TaxonomyVersionORM.status == "active")
            )
            orm = result.scalars().first()
            return self._to_version_info(orm) if orm else None

    async def get_tree(self, version_id: TaxonomyVersionId) -> TaxonomyTree | None:
        version_info = await self.get_version(version_id)
        if version_info is None:
            return None
        async with self._session_factory() as session:
            result = await session.execute(
                select(TaxonomyNodeORM)
                .where(TaxonomyNodeORM.taxonomy_version_id == version_id)
                .order_by(TaxonomyNodeORM.level, TaxonomyNodeORM.printed_code)
            )
            nodes = [self._to_domain_node(n, version_id) for n in result.scalars().all()]
        return TaxonomyTree(version=version_info, nodes=tuple(nodes))

    async def get_stats(self, version_id: TaxonomyVersionId) -> TaxonomyStats | None:
        tree = await self.get_tree(version_id)
        if tree is None:
            return None
        level_3_nodes = [n for n in tree.nodes if n.level == TaxonomyLevel.LEVEL_3]
        code_counter: Counter[str] = Counter(n.printed_code for n in level_3_nodes)
        duplicate_codes = tuple((code, count) for code, count in code_counter.items() if count > 1)
        duplicate_paths: list[tuple[str, tuple[str, ...]]] = []
        for code, _ in duplicate_codes:
            for node in level_3_nodes:
                if node.printed_code == code:
                    duplicate_paths.append((code, node.full_path))
        return TaxonomyStats(
            level_1_count=sum(1 for n in tree.nodes if n.level == TaxonomyLevel.LEVEL_1),
            level_2_count=sum(1 for n in tree.nodes if n.level == TaxonomyLevel.LEVEL_2),
            level_3_count=len(level_3_nodes),
            distinct_level_3_code_count=len(code_counter),
            duplicate_printed_codes=duplicate_codes,
            empty_level_3_name_count=sum(1 for n in level_3_nodes if n.printed_name is None),
            duplicate_printed_code_paths=tuple(duplicate_paths),
        )

    async def get_node(self, node_id: TaxonomyNodeId) -> TaxonomyNode | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(TaxonomyNodeORM).where(TaxonomyNodeORM.node_id == node_id)
            )
            orm = result.scalars().first()
            if orm is None:
                return None
            return self._to_domain_node(orm, TaxonomyVersionId(orm.taxonomy_version_id))

    async def resolve_by_printed_code(
        self, printed_code: str, parent_printed_code: str | None = None
    ) -> CodeResolution:
        async with self._session_factory() as session:
            result = await session.execute(
                select(TaxonomyNodeORM)
                .where(
                    TaxonomyNodeORM.printed_code == printed_code,
                    TaxonomyNodeORM.taxonomy_version_id.in_(
                        select(TaxonomyVersionORM.id).where(TaxonomyVersionORM.status == "active")
                    ),
                )
                .order_by(TaxonomyNodeORM.level, TaxonomyNodeORM.full_path)
            )
            matches = result.scalars().all()

        if not matches:
            return CodeResolution(
                printed_code=printed_code,
                ambiguous=False,
                resolved_node=None,
                candidates=(),
            )

        active_version_id = matches[0].taxonomy_version_id
        candidates = [
            self._to_domain_node(m, TaxonomyVersionId(active_version_id)) for m in matches
        ]

        if len(candidates) == 1:
            return CodeResolution(
                printed_code=printed_code,
                ambiguous=False,
                resolved_node=candidates[0],
                candidates=tuple(candidates),
            )

        if parent_printed_code is not None:
            narrowed = [n for n in candidates if _parent_code(n) == parent_printed_code]
            if len(narrowed) == 1:
                return CodeResolution(
                    printed_code=printed_code,
                    ambiguous=False,
                    resolved_node=narrowed[0],
                    candidates=tuple(candidates),
                )
            return CodeResolution(
                printed_code=printed_code,
                ambiguous=True,
                resolved_node=None,
                candidates=tuple(narrowed) if narrowed else tuple(candidates),
            )

        return CodeResolution(
            printed_code=printed_code,
            ambiguous=True,
            resolved_node=None,
            candidates=tuple(candidates),
        )

    async def resolve_by_full_path(self, full_path: Sequence[str]) -> TaxonomyNode | None:
        target = list(full_path)
        async with self._session_factory() as session:
            result = await session.execute(
                select(TaxonomyNodeORM).where(
                    TaxonomyNodeORM.full_path == target,
                    TaxonomyNodeORM.taxonomy_version_id.in_(
                        select(TaxonomyVersionORM.id).where(TaxonomyVersionORM.status == "active")
                    ),
                )
            )
            orm = result.scalars().first()
            if orm is None:
                return None
            return self._to_domain_node(orm, TaxonomyVersionId(orm.taxonomy_version_id))

    async def create_draft_version(
        self,
        standard_name: str,
        source_sha256: str,
        extracted_resource_sha256: str,
        nodes: Sequence[TaxonomyNode],
    ) -> TaxonomyVersionInfo:
        version_id = uuid4()
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            async with session.begin():
                # 检查是否已存在相同来源的版本
                existing = await session.execute(
                    select(TaxonomyVersionORM).where(
                        TaxonomyVersionORM.source_sha256 == source_sha256,
                        TaxonomyVersionORM.extracted_resource_sha256 == extracted_resource_sha256,
                    )
                )
                existing_orm = existing.scalars().first()
                if existing_orm is not None:
                    return self._to_version_info(existing_orm)

                version_orm = TaxonomyVersionORM(
                    id=version_id,
                    standard_name=standard_name,
                    source_sha256=source_sha256,
                    extracted_resource_sha256=extracted_resource_sha256,
                    status="draft",
                    activated_at=None,
                    level_1_count=0,
                    level_2_count=0,
                    level_3_count=0,
                    distinct_level_3_code_count=0,
                    empty_level_3_name_count=0,
                    duplicate_printed_codes=[],
                    metadata_json={},
                    created_at=now,
                    updated_at=now,
                )
                session.add(version_orm)
                await session.flush()

                # 建立父节点 DB ID 映射
                node_id_to_db_id: dict[str, UUID] = {}
                # 先按 level 升序插入，保证父节点先于子节点
                sorted_nodes = sorted(nodes, key=lambda n: (int(n.level), n.full_path))
                for node in sorted_nodes:
                    db_id = uuid4()
                    node_id_to_db_id[node.node_id] = db_id
                    parent_db_id = (
                        node_id_to_db_id.get(node.parent_node_id) if node.parent_node_id else None
                    )
                    orm = TaxonomyNodeORM(
                        id=db_id,
                        taxonomy_version_id=version_id,
                        node_id=node.node_id,
                        level=int(node.level),
                        printed_code=node.printed_code,
                        printed_name=node.printed_name,
                        parent_node_db_id=parent_db_id,
                        full_path=list(node.full_path),
                        remark=node.remark,
                        source_page=node.source_page,
                        source_anomaly=node.source_anomaly,
                        display_name=node.display_name,
                        display_name_source=node.display_name_source.value,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(orm)
                await session.flush()

                # 写入完整性统计（不激活，仅记录）
                level_3 = [n for n in nodes if n.level == TaxonomyLevel.LEVEL_3]
                code_counter: Counter[str] = Counter(n.printed_code for n in level_3)
                dup_codes = [code for code, count in code_counter.items() if count > 1]
                await session.execute(
                    update(TaxonomyVersionORM)
                    .where(TaxonomyVersionORM.id == version_id)
                    .values(
                        level_1_count=sum(1 for n in nodes if n.level == TaxonomyLevel.LEVEL_1),
                        level_2_count=sum(1 for n in nodes if n.level == TaxonomyLevel.LEVEL_2),
                        level_3_count=len(level_3),
                        distinct_level_3_code_count=len(code_counter),
                        empty_level_3_name_count=sum(1 for n in level_3 if n.printed_name is None),
                        duplicate_printed_codes=dup_codes,
                    )
                )
                await session.flush()

                version_orm = await session.get(TaxonomyVersionORM, version_id)
                assert version_orm is not None
                return self._to_version_info(version_orm)

    async def activate_version(self, version_id: TaxonomyVersionId) -> TaxonomyVersionInfo:
        tree = await self.get_tree(TaxonomyVersionId(version_id))
        if tree is None:
            raise TaxonomyValidationError((f"版本 {version_id} 不存在",))
        stats = await self.get_stats(TaxonomyVersionId(version_id))
        assert stats is not None

        # 执行完整性校验，失败抛 TaxonomyValidationError
        validate_integrity(list(tree.nodes), stats)

        now = datetime.now(UTC)
        async with self._session_factory() as session:
            async with session.begin():
                # 把其他 active 版本标记为 retired
                await session.execute(
                    update(TaxonomyVersionORM)
                    .where(TaxonomyVersionORM.status == "active")
                    .values(status="retired")
                )
                # 激活当前版本
                await session.execute(
                    update(TaxonomyVersionORM)
                    .where(TaxonomyVersionORM.id == version_id)
                    .values(status="active", activated_at=now)
                )
                version_orm = await session.get(TaxonomyVersionORM, version_id)
                assert version_orm is not None
                return self._to_version_info(version_orm)

    async def retire_version(self, version_id: TaxonomyVersionId) -> TaxonomyVersionInfo:
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(TaxonomyVersionORM)
                    .where(TaxonomyVersionORM.id == version_id)
                    .values(status="retired")
                )
                version_orm = await session.get(TaxonomyVersionORM, version_id)
                assert version_orm is not None
                return self._to_version_info(version_orm)

    def _to_version_info(self, orm: TaxonomyVersionORM) -> TaxonomyVersionInfo:
        return TaxonomyVersionInfo(
            version_id=TaxonomyVersionId(orm.id),
            standard_name=orm.standard_name,
            source_sha256=orm.source_sha256,
            extracted_resource_sha256=orm.extracted_resource_sha256,
            status=TaxonomyVersionStatus(orm.status),
            activated_at=orm.activated_at,
            level_1_count=orm.level_1_count,
            level_2_count=orm.level_2_count,
            level_3_count=orm.level_3_count,
            distinct_level_3_code_count=orm.distinct_level_3_code_count,
            duplicate_printed_codes=tuple(orm.duplicate_printed_codes or []),
            empty_level_3_name_count=orm.empty_level_3_name_count,
        )

    def _to_domain_node(self, orm: TaxonomyNodeORM, version_id: TaxonomyVersionId) -> TaxonomyNode:
        full_path = tuple(orm.full_path or ())
        parent_node_id = (
            _derive_parent_node_id(full_path) if orm.parent_node_db_id is not None else None
        )
        return TaxonomyNode(
            node_id=TaxonomyNodeId(orm.node_id),
            taxonomy_version_id=version_id,
            level=TaxonomyLevel(str(orm.level)),
            printed_code=orm.printed_code,
            printed_name=orm.printed_name,
            parent_node_id=parent_node_id,
            full_path=full_path,
            remark=orm.remark,
            source_page=orm.source_page,
            source_anomaly=orm.source_anomaly,
            display_name=orm.display_name,
            display_name_source=DisplayNameSource(orm.display_name_source),
        )


def _derive_parent_node_id(full_path: tuple[str, ...]) -> TaxonomyNodeId | None:
    """从 full_path 推导父节点的 node_id。

    node_id 构造规则：
    - 一级: db44t2479-2024:{level_1_code}  (full_path[0])
    - 二级: db44t2479-2024:{level_2_code}  (full_path[1])
    - 三级: db44t2479-2024:{level_2_code}:{level_3_code}

    因此：
    - 二级节点 (len=2) 的父是一级，parent node_id = db44t2479-2024:{full_path[0]}
    - 三级节点 (len=3) 的父是二级，parent node_id = db44t2479-2024:{full_path[1]}
    """
    if len(full_path) <= 1:
        return None
    if len(full_path) == 2:
        return TaxonomyNodeId(f"db44t2479-2024:{full_path[0]}")
    return TaxonomyNodeId(f"db44t2479-2024:{full_path[1]}")


def _parent_code(node: TaxonomyNode) -> str | None:
    if len(node.full_path) < 2:
        return None
    return node.full_path[-2]
