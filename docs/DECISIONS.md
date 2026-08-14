# DECISIONS.md

# ADR-001: Deterministic pipeline, bounded LLM
Status: accepted

High-volume processing is deterministic handlers/services. LLM is only used for difficult bounded subproblems.

# ADR-002: Obsidian as source, runtime snapshot as hot path
Status: accepted

Per-mention Obsidian calls are prohibited.

# ADR-003: PostgreSQL + pgvector before separate vector DB
Status: accepted

Current corpus size does not justify additional vector infrastructure until benchmark proves a bottleneck.

# ADR-004: AI direct result + optional human correction
Status: accepted

Human review is not a mandatory gate; correction/audit remains.

# ADR-005: Trusted mirrors first, lockfiles remain authoritative
Status: accepted

For dependency downloads, use a trusted regular mirror first when it is materially faster on the deployment network. Preserve upstream package identity, pinned versions and lockfile integrity; record container digests where practical. Fall back to the official source if the mirror is unavailable, and never use an untrusted binary mirror.

# ADR-006: SQLite handoff database compiles the runtime gazetteer snapshot
Status: accepted

The real gazetteer OpenAPI exposes normalization and a batch query, but no entity enumeration/export operation. The handoff SQLite schema is therefore validated and read in `mode=ro` to build a deterministic runtime snapshot. The HTTP adapter discovers the batch operation from `/openapi.json`; it does not guess endpoint names. Snapshot aliases are the hot path, and unresolved mentions are sent in one remote batch call.
