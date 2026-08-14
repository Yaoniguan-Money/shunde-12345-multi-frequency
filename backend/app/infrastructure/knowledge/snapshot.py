import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from backend.app.domain.types import CanonicalEntity, EntityId, GazetteerSnapshot


class SnapshotSourceError(RuntimeError):
    """The source SQLite database is missing or does not match its documented schema."""


def normalize_alias(value: str) -> str:
    return " ".join(value.replace("\ufeff", "").strip().casefold().split())


class GazetteerSnapshotBuilder:
    """Build a deterministic, read-only runtime snapshot from the handoff SQLite database."""

    _required_tables = {
        "places": {"id", "name", "short_name", "type", "adcode"},
        "aliases": {"alias", "place_id", "alias_type"},
        "organizations": {"id", "standard_name", "aliases", "org_type"},
    }

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def build(self) -> GazetteerSnapshot:
        if not self._database_path.is_file():
            raise SnapshotSourceError(f"地名库 SQLite 不存在: {self._database_path}")
        uri = f"file:{self._database_path.resolve().as_posix()}?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True)
        except sqlite3.Error as error:
            raise SnapshotSourceError("无法以只读模式打开地名库 SQLite") from error
        with connection:
            self._validate_schema(connection)
            entities = self._read_entities(connection)
        payload = [
            {
                "id": str(entity.entity_id),
                "name": entity.standard_name,
                "type": entity.entity_type,
                "aliases": sorted(set(entity.aliases)),
            }
            for entity in entities
        ]
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        version = f"sqlite-{self._database_path.stat().st_mtime_ns}-{digest[:12]}"
        return GazetteerSnapshot(
            snapshot_hash=digest,
            version=version,
            built_at=datetime.now(UTC),
            entities=tuple(entities),
        )

    def _validate_schema(self, connection: sqlite3.Connection) -> None:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        missing_tables = set(self._required_tables) - tables
        if missing_tables:
            raise SnapshotSourceError(f"地名库缺少表: {', '.join(sorted(missing_tables))}")
        for table, required in self._required_tables.items():
            columns = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
            missing_columns = required - columns
            if missing_columns:
                raise SnapshotSourceError(
                    f"地名库表 {table} 缺少字段: {', '.join(sorted(missing_columns))}"
                )

    @staticmethod
    def _read_entities(connection: sqlite3.Connection) -> list[CanonicalEntity]:
        aliases_by_place: dict[int, list[str]] = {}
        for alias, place_id in connection.execute(
            "SELECT alias, place_id FROM aliases ORDER BY id"
        ):
            aliases_by_place.setdefault(int(place_id), []).append(str(alias))
        entities: list[CanonicalEntity] = []
        for place_id, name, short_name, entity_type, _adcode in connection.execute(
            "SELECT id, name, short_name, type, adcode FROM places ORDER BY id"
        ):
            values = [str(name)]
            if short_name:
                values.append(str(short_name))
            values.extend(aliases_by_place.get(int(place_id), []))
            entities.append(
                CanonicalEntity(
                    entity_id=EntityId(uuid5(NAMESPACE_URL, f"shunde:places:{place_id}")),
                    standard_name=str(name),
                    entity_type=str(entity_type or "unknown"),
                    aliases=tuple(dict.fromkeys(values)),
                )
            )
        for organization_id, name, aliases_json, organization_type in connection.execute(
            "SELECT id, standard_name, aliases, org_type FROM organizations ORDER BY id"
        ):
            values = [str(name)]
            try:
                parsed = cast(list[object], json.loads(aliases_json or "[]"))
            except (TypeError, json.JSONDecodeError) as error:
                raise SnapshotSourceError(
                    f"机构 {organization_id} aliases 不是合法 JSON"
                ) from error
            if not all(isinstance(item, str) for item in parsed):
                raise SnapshotSourceError(f"机构 {organization_id} aliases 必须是字符串数组")
            values.extend(cast(list[str], parsed))
            entities.append(
                CanonicalEntity(
                    entity_id=EntityId(
                        uuid5(NAMESPACE_URL, f"shunde:organizations:{organization_id}")
                    ),
                    standard_name=str(name),
                    entity_type=str(organization_type or "organization"),
                    aliases=tuple(dict.fromkeys(values)),
                )
            )
        return entities


class RuntimeSnapshotStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def save(self, snapshot: GazetteerSnapshot) -> Path:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "snapshot_hash": snapshot.snapshot_hash,
            "version": snapshot.version,
            "built_at": snapshot.built_at.isoformat(),
            "entities": [
                {
                    "entity_id": str(entity.entity_id),
                    "standard_name": entity.standard_name,
                    "entity_type": entity.entity_type,
                    "aliases": list(entity.aliases),
                }
                for entity in snapshot.entities
            ],
        }
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self._path)
        return self._path

    def load(self) -> GazetteerSnapshot:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            entities = tuple(
                CanonicalEntity(
                    entity_id=EntityId(UUID(item["entity_id"])),
                    standard_name=item["standard_name"],
                    entity_type=item["entity_type"],
                    aliases=tuple(item.get("aliases", [])),
                )
                for item in payload["entities"]
            )
            return GazetteerSnapshot(
                snapshot_hash=payload["snapshot_hash"],
                version=payload["version"],
                built_at=datetime.fromisoformat(payload["built_at"]),
                entities=entities,
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise SnapshotSourceError(f"运行时地名快照不可读: {self._path}") from error
