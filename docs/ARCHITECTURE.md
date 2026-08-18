# ARCHITECTURE.md

## 核心原则

1. 现实事件识别 > 文本相似。
2. Entity ID / Focal Object ID 是连接多种自然语言表达的稳定锚点。
3. Embedding = recall evidence, not judge。
4. 大模型只处理缩小后的困难问题。
5. Obsidian / gazetteer = knowledge source，runtime 使用编译 snapshot。
6. 离线历史建库与在线新工单分离。
7. 所有 AI 输出可追溯到版本与证据。
8. 多频是跨不同 WorkOrder 的现实事件重复，不是单张工单内部 EventInstance 的数量。
9. API 路由是薄的，业务逻辑在 application handlers / domain services。
10. 领域代码不依赖 FastAPI、SQLAlchemy、Obsidian、vLLM、具体模型厂商或前端。
11. 基础设施位于 typed ports / adapters 之后。
12. AI 直接产出多频结果，人工纠正是独立不可变审计层，不强制复核门。
13. 分析状态、标准分类、来源标记是三个独立维度。

本轮（演讲稿对齐总升级计划）的目标架构与旧 Cloud-first Demo Core 不同，旧路径只读保留。新链路 `understanding.v3` 替代 `understanding.v2` 成为 active projection；旧 v1/v2 数据保留审计可达。

当前实现 checkpoint（2026-08-18）：AnalysisScope、V3 understanding 持久化、Provider Profile registry/snapshot、候选路线证据、SameEvent 状态和 overview/facets API 已落地并通过代码门禁；真实 100 条回放、Gold Set 和性能数据仍是 WP8 未执行项。

## Pipeline (V3, target)

```text
Import batch (N work orders, immutable raw text + reported_at)
  -> AnalysisScope freeze (import_batch_id, work_order_id set, target_count,
                            pipeline_version, taxonomy_version,
                            provider_profile_snapshot, execution_policy_snapshot)
  -> WorkOrderUnderstandingV3
     -> Segment (current_complaint / current_request / history_context / department_reply)
     -> Extract EventFact[] (only from current_complaint + current_request)
     -> Field-level evidence span validation
  -> Standard Classification
     -> if source code present: deterministic taxonomy lookup + hierarchy validation
     -> else: taxonomy-constrained provider classification (node_id only)
  -> Reality Object Resolution (project / org / place / product / road)
     -> batch alias assertion with provenance
  -> Embedding (retrieval evidence only)
  -> CandidateGenerator (mixed bounded, no O(N^2))
  -> SameEventJudgeV2 (structured, hard anchor gate)
  -> ClusterAssembler (group-level consistency, consensus narrative)
  -> FrequencyPolicy.v2 (reported_at 3-day window, distinct work_order_id)
  -> Active projection (read API, frontend, export)
```

## Ports / Adapters

- `GazetteerProvider` / `MentionResolver` / `RealityObjectResolver`
- `LLMProvider` / `EmbeddingProvider` / `RerankerProvider`
- `WorkOrderSegmenter` / `EventFactExtractor` / `ClassificationProvider`
- `SameEventMatcher` / `ClusterConsistencyChecker`
- `TaxonomyRepository` / `WorkOrderRepository` / `EventRepository` / `JobRepository`
- `ProviderProfileRegistry` / `AnalysisScopeRepository`
- `HumanCorrectionRepository` / `AuditLogRepository`
- `Exporter`

Application handlers 依赖 ports；infrastructure 实现 adapters。任何模型厂商名称只出现在 cloud profile 配置和安全展示，不进入 SameEvent、分类、聚类或领域服务代码。

## Provider Profile Registry

任务前选择，任务中锁定：

```text
ProviderProfile
  profile_id
  deployment_kind: local | cloud
  display_name
  llm_adapter + model_id
  embedding_adapter + model_id
  structured_output_capability
  configured
  last_validation_status: configured | validated | unavailable | validation_failed
  last_validated_at
  redacted_service_description
  configuration_version
  execution_policy
```

前端只传 `profile_id`，不能传 API Key 或任意 Base URL。任务保存完整脱敏快照。业务服务只依赖 Provider 端口，不出现 `qwen` / `dashscope` 等厂商字符串。

Execution Policy 按部署分离：

```text
understanding_concurrency
classification_concurrency
embedding_batch_size
retrieval_concurrency
same_event_concurrency
db_read_batch_size
db_write_batch_size
max_candidates_per_event
request_timeout
rate_limit_rpm
rate_limit_tpm
```

云端策略使用持久化 HTTP client 与连接池；本地策略默认保持单 LLM in-flight，不通过多并发生成请求增加 KV Cache。

## Taxonomy (DB44/T 2479—2024 附录 A)

版本化主数据：

```text
TaxonomyVersion
  version_id
  standard_name
  source_sha256
  extracted_resource_sha256
  status: draft | active | retired
  activated_at

TaxonomyNode
  node_id
  taxonomy_version_id
  level: 1 | 2 | 3
  printed_code
  printed_name   (nullable for 13 empty level-3 names)
  parent_node_id
  remark
  source_page
  source_anomaly
```

- 14 一级、99 二级、515 三级记录；514 个不同印刷三级代码。
- `090499` 两条不同父路径保留：`db44t2479-2024:0904:090499` 与 `db44t2479-2024:0905:090499`。
- 13 条空三级名称保真，不伪造标准名；前端可用继承显示规则。
- 激活校验失败必须拒绝，不能加载半份目录。
- 来源代码确定性映射；无代码时分类器只能选 `classification_node_id`。

## WorkOrder / EventInstance V3

WorkOrder 不可变，新增字段：

- `import_batch_id`、`external_work_order_number`
- `raw_title`、`raw_content`，不可变
- `reported_at` + `reported_at_source` + `reported_at_parser_version`
- `imported_at`
- `source_tags`（只保存标题/渠道事实）
- `raw_payload_hash`

EventInstance V3 至少保存：

- `work_order_id`、`pipeline_version`
- `current_problem`、`current_request`
- `classification_node_id` + `classification_source` (`source_code | model | human`) + `classification_confidence` + 歧义状态
- `focal_object_mentions`、`responsible_party_mentions`、`location_mentions`
- `occurrence_interval`、`history_context`、`previous_work_order_references`
- 字段级 `evidence_spans`、`unknown_fields`
- Provider / 模型 / prompt / schema / 知识快照版本

标准分类绑定在 EventInstance，不在 WorkOrder。工单列表上的“诉求事项分类”是当前有效事项的聚合投影。

ReportedAtResolver 按固定优先级：
1. 导入文件中经字段合同确认的正式受理/反映时间；
2. 经来源系统格式合同验证的工单号日期解析器；
3. 明确 `unknown`。

历史回复日期、事发时间、导入时间均不能替代 `reported_at` 计算三天三单。

## AnalysisScope 与 Job

任务创建时冻结：

- 导入批次；
- 成功工单的稳定 ID 集合或内容指纹；
- `target_work_order_count`；
- pipeline version；
- taxonomy version；
- Provider Profile 快照；
- Execution Policy 快照。

任务可分块、断点恢复、幂等重跑，但 target scope 不可变化。部分工单失败时任务状态为 `completed_with_failures`，不可伪装全部完成。

## Same Event、聚类与高频

`SameEventJudgeV2` 结构化输出包含 `same_focal_object / same_responsible_party / same_classification / report_window_compatible / same_handling_chain / same_location / claimant_variation_compatible / contradictions[] / unknowns[] / final_decision / confidence / evidence_refs[]`。

正向结论必须满足焦点对象已确认相同、标准分类相同或受控规则声明兼容、`reported_at` 时间兼容、每个 true 字段引用双方证据、不存在硬冲突。关键锚点缺失返回 `ambiguous`，不进入自动聚类正向边。

`ClusterAssembler` 只消费 V2 判定的有效正向边和人工确认边；不使用纯传递闭包；成员工单数使用 `COUNT(DISTINCT work_order_id)`。

`FrequencyPolicy.v2` 状态机只有：

- `high_frequency`：证据证明达到门槛；
- `not_reached`：有效日期足以计算，但所有三日窗口都不足 3 张；
- `insufficient_date_evidence`：日期缺失，不能可靠判断。

`low_frequency` 不存在于数据库、API、前端枚举中。

## 版本与投影

```text
understanding.v3
classification.db44t2479-2024.v1
object-resolution.v2
same-event.v2
frequency-policy.v2
cluster.v2
```

每条结果可追溯到原文哈希、导入批次、taxonomy、provider、模型、prompt、schema、候选策略、同事件策略和知识快照。旧 V2 数据只读保留；页面默认读取 active pipeline projection。

## 人工纠正

人工纠正是独立、不可变、可审计记录：分类确认/纠正、对象别名确认/否决、同事件确认/否决、聚类合并/拆分、处置记录。模型重跑应用纠正投影，不能覆盖操作者、时间、理由和原始纠正内容。

## Port allocation

- Gazetteer local service: `127.0.0.1:8000`
- Main backend: `127.0.0.1:8080`
- Frontend dev: `127.0.0.1:5173`
- PostgreSQL: `127.0.0.1:5432`
- Model server (Ollama / cloud): configurable, do not collide with 8000/8080
