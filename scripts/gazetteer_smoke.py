"""Build a runtime snapshot and call the real OpenAPI batch endpoint."""

import asyncio
import json
import os
from pathlib import Path

from backend.app.infrastructure.knowledge.gazetteer import GazetteerHttpAdapter
from backend.app.infrastructure.knowledge.snapshot import (
    GazetteerSnapshotBuilder,
    RuntimeSnapshotStore,
)


async def main() -> None:
    database_path = Path(os.environ["SHUNDE_GAZETTEER_DB"])
    snapshot_path = Path(
        os.environ.get("SHUNDE_GAZETTEER_SNAPSHOT", "data/runtime/gazetteer.snapshot.json")
    )
    base_url = os.environ.get("SHUNDE_GAZETTEER_API", "http://127.0.0.1:8000")
    snapshot = GazetteerSnapshotBuilder(database_path).build()
    RuntimeSnapshotStore(snapshot_path).save(snapshot)
    adapter = GazetteerHttpAdapter(base_url, timeout_seconds=5.0)
    health = await adapter.health()
    results = await adapter.lookup_many(("凤城", "人民医院", "未知地点"))
    print(
        json.dumps(
            {
                "health": {"available": health.available, "version": health.version},
                "snapshot_entity_count": len(snapshot.entities),
                "snapshot_hash": snapshot.snapshot_hash,
                "results": [
                    {
                        "mention": result.mention,
                        "state": result.state.value,
                        "candidates": [
                            candidate.entity.standard_name for candidate in result.candidates
                        ],
                    }
                    for result in results
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
