import sqlite3
from pathlib import Path

from backend.app.domain.types import (
    EntityCandidateSet,
    GazetteerHealth,
    GazetteerSnapshot,
    ResolutionState,
)
from backend.app.infrastructure.knowledge.resolver import RuntimeEntityResolver
from backend.app.infrastructure.knowledge.snapshot import (
    GazetteerSnapshotBuilder,
    RuntimeSnapshotStore,
)


def _create_source(path: Path) -> None:
    connection = sqlite3.connect(path)
    with connection:
        connection.executescript(
            """
            CREATE TABLE places (id INTEGER PRIMARY KEY, name TEXT NOT NULL, short_name TEXT,
              type TEXT, parent_code TEXT, adcode TEXT, level INTEGER);
            CREATE TABLE aliases (id INTEGER PRIMARY KEY, alias TEXT NOT NULL,
              place_id INTEGER NOT NULL, alias_type TEXT, note TEXT);
            CREATE TABLE organizations (id INTEGER PRIMARY KEY, standard_name TEXT NOT NULL,
              aliases TEXT, org_type TEXT, district TEXT, address TEXT, note TEXT);
            INSERT INTO places VALUES (1, '大良街道', '大良', '街道', NULL, '440606004000', 2);
            INSERT INTO aliases VALUES (1, '凤城', 1, '俗称', NULL);
            INSERT INTO organizations VALUES
              (1, '南方医科大学顺德医院', '["人民医院", "顺德医院"]', '医院', NULL, NULL, NULL);
            """
        )


async def test_snapshot_is_deterministic_and_runtime_resolver_batches_unknown(
    tmp_path: Path,
) -> None:
    source = tmp_path / "shunde_places.db"
    _create_source(source)
    snapshot = GazetteerSnapshotBuilder(source).build()
    output = RuntimeSnapshotStore(tmp_path / "snapshot.json")
    output.save(snapshot)
    loaded = output.load()

    assert loaded.snapshot_hash == snapshot.snapshot_hash
    assert len(loaded.entities) == 2

    class RecordingRemote:
        def __init__(self) -> None:
            self.calls: list[tuple[str, ...]] = []

        async def health(self) -> GazetteerHealth:
            return GazetteerHealth(True, "test")

        async def snapshot(self) -> GazetteerSnapshot:
            return loaded

        async def lookup_many(self, mentions: tuple[str, ...]) -> tuple[EntityCandidateSet, ...]:
            self.calls.append(mentions)
            return tuple(
                EntityCandidateSet(mention, ResolutionState.UNRESOLVED) for mention in mentions
            )

    remote = RecordingRemote()
    resolver = RuntimeEntityResolver(loaded, remote)

    results = await resolver.resolve_many(("凤城", "未知一", "未知二"))

    assert results[0].state.value == "resolved"
    assert results[0].candidates[0].entity.standard_name == "大良街道"
    assert remote.calls == [("未知一", "未知二")]
