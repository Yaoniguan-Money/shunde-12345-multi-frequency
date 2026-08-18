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
Status: superseded by ADR-019 and ADR-020

历史背景：比赛 Demo 使用 remote Qwen understanding/embedding/SameEvent，因为操作者显式设置 `SHUNDE_AI_PROVIDER_MODE=remote`。这是 bounded sample path，不是全量声明；local 仍是安全默认，没有自动 fallback，没有厂商特化 handler，API key 不进源码/日志/数据库。

本轮取代原因：演讲稿对齐总升级计划要求每次任务前在 UI 选择 Provider Profile 并冻结快照，不再依赖全局环境变量切换；旧 cloud-first Demo Core 的 `AI_PROVIDER_MODE` 全局开关被 ProviderProfileRegistry 取代。旧 Demo Core 路径只读保留，新任务必须通过 Provider Profile 创建。

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
Status: superseded by ADR-019 and ADR-021

历史背景：Demo UI 通过 `POST /analysis-jobs` 启动 AI 分析并轮询 `GET /analysis-jobs/{job_id}`。单进程 asyncio 任务复用既有 `AnalysisJob`/`AnalysisRun`/checkpoint，调用与 `scripts/demo_core.py` 相同的 `DemoAnalysisOrchestrator`；HTTP 层不重复模型/检索/聚类逻辑。每个请求必须带 `max_work_orders` 且硬限 1–300。

本轮取代原因：演讲稿对齐计划删除产品层研判数量上限。成功导入 N 张工单就研判全部 N 张；`max_work_orders` 与 `selection_mode` 从请求体移除。后端可分块、限并发、断点续跑，但不可截断目标范围后伪装完成。

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
Status: superseded by ADR-019

历史背景：Demo 任务可显式选择 `recurrence_candidates`，扫描导入批次中的确定性复发词或被引用工单号，返回请求的 1–300 行。选择模式和已选数量属于 job trace。这种低成本路由从不产生 SameEvent 证据。

本轮取代原因：演讲稿对齐计划删除 `selection_mode` 与 `max_work_orders`。研判范围就是导入批次全部成功工单；不再有 bounded recurrence routing 这个产品层概念。底层仍可用确定性候选缩小 SameEvent 候选集，但不再是任务创建时的产品参数。

# ADR-016: Cluster identity and human review survive projection changes
Status: accepted

New clusters have a deterministic signature over their EventInstance member set,
so overlapping analysis runs reuse the same cluster instead of inflating product
counts. Human `review_status` is independent of `handling_status`. Removing a
member may make a cluster inactive in the multi-frequency list, but direct detail
access, corrections and handling history remain available so the operator can
undo the decision. Reruns do not silently restore human-removed membership.

# ADR-017: One bounded analysis owns one durable lifecycle
Status: accepted

The HTTP analysis job is the terminal owner of understanding, embedding,
retrieval, SameEvent matching and clustering. Sub-pipelines receive the existing
`AnalysisJob`/`AnalysisRun`; they may checkpoint progress but cannot create a
hidden graph job or mark the outer job complete. SameEvent edges are persisted
as each remote decision completes and retries skip pairs already stored for the
same run. Request bounds and cumulative progress live in the existing run JSONB
metrics so queued/running work can be reconstructed after process restart
without a schema migration. Only the outer application service writes completed
or failed, preventing the UI from observing completed before graph persistence.

# ADR-018: High frequency is a backend rolling-calendar projection
Status: superseded by ADR-024

历史背景：高频不由客户端从相似度/总成员数/事件卡片推断。catalog 对每个 active cluster 计算其解析到 `occurrence_date` 的不同 WorkOrder 在任意包含首尾的三日历日窗口内的最大数量，达到 3 返回 `is_high_frequency=true`，没有解析日期的 EventInstance 不计入，同 WorkOrder 多事件只计一次。API 返回窗口大小和观测计数用于审计。

本轮取代原因：演讲稿对齐计划把高频计数时间字段从 `occurrence_date`（事发时间）改为 `reported_at`（受理时间）。`occurrence_date` 可能未知或为区间，不能作为高频门槛的稳定依据。其余三日窗口、不同 WorkOrder 去重、`high_frequency / not_reached / insufficient_date_evidence` 三态语义保持不变，并显式禁止 `low_frequency` 枚举。

---

# 演讲稿对齐总升级计划 ADR（ADR-019 至 ADR-026）

以下 ADR 来自 `docs/presentation-alignment-plan/00-LOCKED-DECISIONS.md`，是本轮所有专项计划的共同上游。若实现与本节冲突，以本节为准，并先更新 ADR。

# ADR-019: 全批次研判，任务前 Provider Profile 选择
Status: accepted

一个导入批次成功导入 N 张工单，研判目标范围就是这 N 张；前端删除“研判数量”输入，API 删除 `max_work_orders` 与 `selection_mode`。用户在每次任务开始前选择“本地模型”或“云端模型”，任务创建时持久化 Provider Profile 快照，任务运行中不可切换。下一次任务可重新选择，不依赖修改全局环境变量。本地路径必须真实执行 LLM、Embedding、结构化输出和最小端到端研判，不能只做 ping/health；云端当前适配千问，支持通过显式 `SHUNDE_AI_REMOTE_FLASH_LLM_MODEL_ID` 选择 Flash 模型，但领域层、任务处理器和数据模型不出现厂商分支。任一模型失败都不得静默切换或返回规则伪造结果。

# ADR-020: ProviderProfileRegistry 与 per-job 快照
Status: accepted

服务端维护安全的 Provider Profile：`profile_id / deployment_kind / display_name / llm_adapter+model_id / embedding_adapter+model_id / structured_output_capability / configured / last_validation_status / last_validated_at / redacted_service_description / configuration_version / execution_policy`。前端只传 `profile_id`，不能传 API Key 或任意 Base URL。任务保存完整脱敏快照，避免配置变更影响运行中的任务。业务服务只依赖 Provider 端口；千问名称只出现在 cloud profile 配置和安全展示，不进入 SameEvent、分类或聚类领域代码。验证使用不含政府数据的极小合成样本，必须真实执行 LLM 结构化 EventFact 输出、DB44 分类节点约束输出、Embedding 输出和维度合同、SameEvent 结构化判断、最小导入夹具到聚类投影的端到端链路，并记录所有实际调用的 provider 证明没有跨 provider fallback。

# ADR-021: AnalysisScope 冻结与不可截断
Status: accepted

任务创建时冻结：导入批次、成功工单的稳定 ID 集合或内容指纹、`target_work_order_count`、pipeline version、taxonomy version、Provider Profile 快照、Execution Policy 快照。任务可分块、断点恢复、幂等重跑，但 target scope 不可变化。部分工单失败时任务状态为 `completed_with_failures`，不可伪装全部完成。资源不足时任务明确排队或失败，不得截断后返回“完成”。

# ADR-022: DB44/T 2479—2024 附录 A 作为版本化主数据
Status: accepted

类型体系完整对齐附录 A：14 个一级、99 个二级、515 条三级记录；514 个不同印刷三级代码。目录使用 `TaxonomyVersion / TaxonomyNode`，分类关系使用 `node_id` 而非中文名称或印刷代码。`090499` 两条不同父路径必须保留：`db44t2479-2024:0904:090499`（民政社区/生活服务）与 `db44t2479-2024:0905:090499`（民政社区/民族宗教），不得擅自改成 `090599`。13 条空三级名称保真，不伪造标准名；前端可用继承显示规则，但不得反向改写标准目录。激活校验失败必须拒绝激活，不能加载半份目录继续运行。

# ADR-023: 分类入口与三态分离
Status: accepted

来源已带有效标准代码时走确定性路径：normalize -> taxonomy lookup -> hierarchy validation -> `classification_node_id`，不调用模型；`090499` 等歧义代码必须结合来源父级代码或完整路径，无法唯一定位时明确 `ambiguous_source_code`。来源没有代码时走 taxonomy-constrained provider 分类：候选缩小 -> bounded provider classification -> `classification_node_id` only -> taxonomy validator；模型输出不能直接携带自创中文类型。`resolved / ambiguous / unresolved / human_corrected` 是真实业务状态，不得自动塞进“其他”伪装成功。分析状态（`unprocessed / analyzed_no_event / analyzed / failed`）、标准分类（节点）、来源标记（`title_tags`）是三个独立维度，不可混用。`title_tags` 只能叫“来源标记”，不能再显示为“类型标签”。

# ADR-024: 高频规则——reported_at 三日窗口，不同工单，无 low_frequency
Status: accepted

高频事件定义为：同一事件在任意连续 3 个自然日内达到 3 张及以上不同工单。窗口使用来源系统的 `reported_at`；历史回复日期、事发日期和导入时间不能替代。算法：取每个不同 `work_order_id` 的有效 `reported_at` 日期，对每个起始日 D 计算 `D <= reported_date <= D + 2 days` 范围内的不同 `work_order_id` 数，达到 3 即 `high_frequency` 并持久化 winning window 和 members。同一天 5 张工单计 5 单；一张工单拆出 3 个事项仍只计 1 单。状态机只有 `high_frequency / not_reached / insufficient_date_evidence`；数据库、API 和前端枚举中不得出现 `low_frequency`。聚类成员变化、`reported_at` 合法纠正、人工合并/拆分、active pipeline 切换、same-event 纠正生效都必须用同一 policy version 重算。

# ADR-025: SameEventJudgeV2 与有界候选
Status: accepted

候选集合由 6 个通道并集产生：canonical focal object 相同、项目/组织别名归一相同、标准分类+行政区域+`reported_at` 窗口兼容、引用同一历史工单号或处置链、结构化专名和关键词检索、normalized summary Embedding top-k。每条候选保存 `retrieval_routes / 各通道分数 / 结构化锚点 / 召回版本 / 被截断或保留的原因`。禁止全库 O(N²) 两两比较；限制的是每个事项候选数和模型调用并发，不是导入批次工单总数。进入模型前的确定性约束（双方焦点对象均已确定且不同、双方具体地点均已确定且冲突、标准分类明确不兼容、时间窗明确不兼容、仅共享通用问题词或短品牌词、人工已有不可变的 not-same 纠正）可直接排除，不消耗 SameEvent LLM。`SameEventJudgeV2` 结构化输出至少包含 `same_focal_object / same_responsible_party / same_classification / report_window_compatible / same_handling_chain / same_location / claimant_variation_compatible / contradictions[] / unknowns[] / final_decision / confidence / evidence_refs[]`。关键锚点缺失返回 `ambiguous`，不进入自动聚类正向边。Embedding 分数不能直接创建同事件边。

# ADR-026: ClusterAssembler 与共识命名
Status: accepted

聚类只消费 V2 判定的有效正向边和人工确认边；pipeline、taxonomy、same-event policy 版本一致；新成员加入后不得与组内强共识冲突；成员工单数使用 `COUNT(DISTINCT work_order_id)`；一张工单中的多个事项不能把频次抬高；人工拆分/合并通过独立审计投影，不覆盖模型边。不能只用传递闭包把 A≈B、B≈C 自动推成 A≈C；组件形成后必须执行组级一致性检查。组名和“为什么关联”从组内共识生成（canonical focal object、标准分类、受理时间窗口、可选行政区域、项目别名证据），禁止取最长成员摘要作为组名。
## ADR-027 — WP2→WP8 active pipeline and provider/task binding (2026-08-18)

- `understanding.v3` is the active pipeline; v1/v2 remain read-only historical projections.
- An analysis job freezes the successful work-order ID set, pipeline, provider profile and execution policy. Resume/retry consumes the same scope.
- Provider profiles are explicitly validated and persisted; local/cloud failures are terminal for that route and never silently fall back.
- Embeddings persist bounded recall evidence only. SameEvent decisions require structured evidence and hard-anchor checks; ambiguous decisions are not positive edges.
- Catalog overview/facets are database projections. Page size is not a business total.

Evidence at this checkpoint: backend 89 tests, frontend 33 tests, Ruff/Pyright/frontend build all pass. Real 100-work-order replay and Gold Set evidence remain pending and are not implied by this ADR.
