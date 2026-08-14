"""Knowledge-source adapters and immutable runtime snapshot tooling."""

from backend.app.infrastructure.knowledge.gazetteer import GazetteerHttpAdapter
from backend.app.infrastructure.knowledge.resolver import RuntimeEntityResolver
from backend.app.infrastructure.knowledge.snapshot import (
    GazetteerSnapshotBuilder,
    RuntimeSnapshotStore,
)

__all__ = [
    "GazetteerHttpAdapter",
    "GazetteerSnapshotBuilder",
    "RuntimeEntityResolver",
    "RuntimeSnapshotStore",
]
