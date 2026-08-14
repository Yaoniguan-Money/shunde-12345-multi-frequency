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

## Port allocation

- Gazetteer local service: `127.0.0.1:8000` (existing)
- Main backend: `127.0.0.1:8080`
- Frontend dev: `127.0.0.1:5173`
- PostgreSQL: `127.0.0.1:5432`
- Model server: configurable, do not collide with 8000/8080
