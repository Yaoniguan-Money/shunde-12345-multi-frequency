# ARCHITECTURE.md

## 核心原则

1. 现实事件识别 > 文本相似。
2. Entity ID 是连接多种自然语言表达的稳定锚点。
3. Embedding = recall evidence, not judge。
4. 大模型只处理缩小后的困难问题。
5. Obsidian = knowledge source，runtime 使用编译 snapshot。
6. 离线历史建库与在线新工单分离。
7. 所有 AI 输出可追溯到版本与证据。

## Pipeline

```text
Raw Work Order
  -> Segment
  -> Extract mentions/events
  -> Batch Entity Resolve
     -> Alias Aho-Corasick
     -> RapidFuzz
     -> Entity Embedding Top-K
     -> one LLM batch for unresolved ambiguity
  -> Canonical Event
  -> Candidate Retrieval
  -> Rerank
  -> SameEventMatcher
  -> Event Relation Graph
  -> Cluster consistency
  -> Multi-frequency event
```

## Ports / Adapters

- GazetteerProvider
- LLMProvider
- EmbeddingProvider
- RerankerProvider
- WorkOrderRepository
- EventRepository
- JobRepository
- Exporter

Application handlers depend on ports; infrastructure implements adapters.

### AI provider routing seam

`LLMProvider`, `EmbeddingProvider` and `RerankerProvider` are the stable application
boundary. `infrastructure/ai/factory.py` composes local and generic remote
OpenAI-compatible adapters without exposing vendor names to handlers:

```text
AI_PROVIDER_MODE=local (default)  -> local adapter only
AI_PROVIDER_MODE=remote           -> remote adapter only (explicit API key)
AI_PROVIDER_MODE=hybrid           -> AUTO/LOCAL local; explicit REMOTE remote
```

There is no failure-triggered cloud fallback and no confidence threshold in the
hybrid policy. Every model result carries provider/model/config/schema/pipeline
trace; API keys never enter traces, logs or database正文. Local public URLs remain
rejected. The remote base URL is configured explicitly (for example, Qwen
DashScope's OpenAI-compatible `/compatible-mode/v1` endpoint).

### Cloud-first Demo Core path

The competition/demo runtime deliberately selects `AI_PROVIDER_MODE=remote` in
its process environment. The current proven path is:

```text
real PostgreSQL sample
  -> understanding.v2 (qwen-plus, structured JSON)
  -> runtime gazetteer batch resolve
  -> qwen3.7-text-embedding (1024 dimensions)
  -> pgvector candidate recall (model/dimension partial HNSW index)
  -> Remote SameEventMatcher (qwen-plus, explicit REMOTE route)
  -> EventMatchEdge trace
  -> complete-link / contradiction-guarded EventCluster
  -> read-only catalog API
```

This is a bounded Demo Core, not a full-corpus claim. The remote provider receives
only explicitly selected demo rows; a local failure never triggers a cloud retry,
and no endpoint or vendor is referenced from an application handler.

### Understanding v2 event contract

An event stores `event_type`, event-specific `behavior`,
`normalized_summary`, `location_signals`, `time_signals`, `mention_indexes` and
raw evidence items. Each evidence item carries a segment ordinal/type, quote and
offsets. The understanding service accepts a model quote only when it is an exact
contiguous substring of the corresponding segmented raw text; fabricated quotes
are discarded before persistence. SameEventMatcher consumes these structured
fields plus canonical entity IDs and never treats an embedding score as a final
decision.

### Same-event and cluster contract

`RemoteSameEventMatcher` returns `same_event`, confidence and explicit evidence
(`same_entity`, `same_location`, `same_issue`, `time_compatible`,
`contradictions`) with a full provider/model/config/schema/pipeline trace. The
matcher is instructed that recurring unresolved complaints at the same place can
be one underlying issue even when dates differ, while same subject does not erase
different issue/behavior evidence. `EventClusterBuilder` uses positive edges but
rejects a merge that would create disjoint canonical entities, disjoint locations,
or incompatible event types; this prevents an A~B/B~C transitive contradiction.

### Read API boundary

The backend exposes typed, read-only projections at `/work-orders`, `/events` and
`/multi-frequency-events` (list/detail). Raw work-order text remains immutable and
is returned only by explicit detail endpoints. Derived event evidence, normalized
entities, match edges, handling status and AI trace stay separate so a frontend
cannot mistake a similarity score for a business decision.

## Port allocation

- Gazetteer local service: `127.0.0.1:8000` (existing)
- Main backend: `127.0.0.1:8080`
- Frontend dev: `127.0.0.1:5173`
- PostgreSQL: `127.0.0.1:5432`
- Model server: configurable, do not collide with 8000/8080
