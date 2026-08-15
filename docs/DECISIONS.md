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

# ADR-007: Local Ollama is the default model runtime
Status: accepted, superseded by ADR-008 for provider selection

The default model mode remains local Ollama/local OpenAI-compatible. The current baseline models are `qwen2.5:3b` for Chinese structured extraction and `nomic-embed-text` for 768-dimensional vectors. Local adapters reject public URLs and never fall back to a cloud service.

# ADR-008: Explicit, auditable local/remote/hybrid providers
Status: accepted

All model calls remain behind `LLMProvider`, `EmbeddingProvider` and `RerankerProvider`. `AI_PROVIDER_MODE` is explicitly `local` (default), `remote` or `hybrid`; remote adapters are generic OpenAI-compatible adapters and receive API keys only from `SecretStr` environment configuration. Hybrid routing has an explicit route seam: `AUTO`/`LOCAL` stays local and `REMOTE` is allowed only when the mode enables it. A failed local call never triggers an implicit remote retry. Provider, model ID, configuration hash, schema version, pipeline version and knowledge snapshot are persisted as trace fields. This phase does not invent a confidence threshold.

# ADR-009: Understanding v2 keeps auditable event evidence
Status: accepted

SameEventMatcher cannot audit a thin summary alone. The event projection therefore
keeps event-specific `behavior` and `time_signals`, mention indexes, and evidence
items tied to a segment ordinal/type with offsets. A model-proposed quote is
persisted only when it is an exact contiguous substring of that segmented raw
text; invalid quotes are discarded. Existing event columns already provide the
storage boundary, so this change required a pipeline/schema version bump rather
than a destructive domain rewrite.

# ADR-010: Cloud-first is an explicit Demo Core mode
Status: accepted

The competition demo uses remote Qwen understanding, embedding and SameEvent
matching because the operator explicitly configured `SHUNDE_AI_PROVIDER_MODE=remote`.
This is a bounded sample path over real PostgreSQL rows, not a full-corpus claim.
Local remains the safe code default when remote is absent; there is no automatic
fallback, no vendor-specific handler code, and no API key in source/logs/database
正文. The proven embedding model/dimension receives its own pgvector HNSW partial
index so dimensions cannot be mixed accidentally.
