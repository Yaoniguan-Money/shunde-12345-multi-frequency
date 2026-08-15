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

# ADR-011: Human review is an audited overlay on derived clusters
Status: accepted

Handling changes append an `EventHandlingRecord` and update only the derived
`EventCluster.handling_status`; human membership decisions append a
`HumanCorrection`, update only `EventClusterMember`, and append an `AuditLog`.
Raw work-order columns are never written by these commands. The event-graph
writer creates a new cluster projection for each analysis run instead of
updating or deleting a corrected cluster, so the correction fact and its old
projection survive reruns rather than being silently overwritten. Current
product scope intentionally exposes only `remove_member` and `confirm_member`;
merge/split requires a separate domain decision and reconciliation contract.

# ADR-012: Bounded HTTP analysis jobs reuse the Demo application seam
Status: accepted

The Demo UI starts AI analysis through `POST /analysis-jobs` and polls
`GET /analysis-jobs/{job_id}`. A single-process asyncio task uses the existing
durable `AnalysisJob`/`AnalysisRun`/checkpoint records and calls the same
`DemoAnalysisOrchestrator` as `scripts/demo_core.py`; the HTTP layer does not
duplicate model, retrieval or clustering logic. Every request must carry an
explicit `max_work_orders` bounded to 1–300, and the Demo route requires an
explicit remote provider configuration with no local/cloud fallback.

# ADR-013: Multi-frequency is counted over distinct WorkOrders
Status: accepted

A WorkOrder is the immutable frequency unit; an EventInstance is an AI-derived
issue inside that WorkOrder. One WorkOrder may legitimately produce several
EventInstances, but those events must not match each other or make that WorkOrder
look repeatedly reported. Retrieval, SameEvent matching and graph construction
therefore accept only pairs from different WorkOrders, and cluster construction
and persistence require at least two distinct WorkOrder IDs.

Cluster membership remains event-level so evidence and human corrections retain
their existing identity. Product projections count distinct WorkOrders separately
from EventInstances: `work_order_count` is the frequency count, `event_count` is
the supporting AI-event count, and compatibility `member_count` has the same
meaning as `work_order_count`. Detail projections group events by WorkOrder to
avoid duplicating immutable raw content. Legacy invalid stored clusters are kept
for audit history but excluded from product Catalog responses; this decision does
not rewrite raw work orders or historical AI records.

# ADR-014: Product truth is a current-pipeline projection with explicit outcomes
Status: accepted

Imported WorkOrders are not implicitly AI-analyzed. Each pipeline run records an
auditable per-WorkOrder outcome (`analyzed`, `analyzed_no_event` or `failed`), and
absence of that record means `unprocessed`. Product Catalog projections use only
the configured current analysis pipeline; historical EventInstances remain
available only through explicit technical pipeline queries. This avoids both
v1/v2 double counting and the false claim that an imported corpus was fully
analyzed.

# ADR-015: Bounded recurrence selection is evidence routing, not judgment
Status: accepted

Demo jobs may explicitly choose `recurrence_candidates`, which scans the import
batch for deterministic recurrence phrases or referenced work-order numbers and
returns only the requested 1–300 rows. Selection mode and selected count are part
of the job trace. This inexpensive routing never creates SameEvent evidence;
understanding, embedding retrieval, SameEventMatcher and cluster consistency
remain the only conclusion path. Sequential selection remains the compatibility
default.

# ADR-016: Cluster identity and human review survive projection changes
Status: accepted

New clusters have a deterministic signature over their EventInstance member set,
so overlapping analysis runs reuse the same cluster instead of inflating product
counts. Human `review_status` is independent of `handling_status`. Removing a
member may make a cluster inactive in the multi-frequency list, but direct detail
access, corrections and handling history remain available so the operator can
undo the decision. Reruns do not silently restore human-removed membership.
