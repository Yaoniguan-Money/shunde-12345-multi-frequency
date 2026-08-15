# 02｜领域模型、数据、时间与迁移

## 1. 统一领域语言

| 领域对象 | 精确定义 | 页面用语 |
|---|---|---|
| Work Order | 一张不可变的原始 12345 工单，也是高频计数单位 | 工单 |
| Event Instance | AI 从一张工单中识别出的一个独立当前问题 | AI 研判事项 |
| Focal Object | 本次投诉指向的项目、场所、企业、道路、产品等现实对象 | 涉及对象/项目 |
| Classification Node | DB44/T 附录 A 某个版本中的唯一目录节点 | 诉求事项分类 |
| Same Event Cluster | 同一现实对象、同类问题、兼容时间窗形成的集中问题组 | 关联事件 |
| Frequency Status | 按不同工单和受理时间计算的门槛结果 | 高频状态 |
| Reported At | 来源系统中的反映/受理时间 | 受理时间 |
| Occurrence Time | 群众描述的问题实际发生时间，可未知或为区间 | 事发时间 |
| Imported At | 本系统导入该行的时间 | 导入时间 |
| Analysis Outcome | 未处理、已分析无事项、已分析、失败 | 分析状态 |
| Handling Status | 业务处置进展，与 AI 判断状态分离 | 处置状态 |

## 2. 一张工单可以有多个事项

关系固定为：

```text
WorkOrder 1 ---- N EventInstance
```

当前 100 条真实数据中：

- 98 张各产生 1 个事项；
- 1 张产生 2 个事项；
- 1 张产生 3 个事项；
- 合计 `98 × 1 + 2 + 3 = 103` 个事项。

这不是异常。统计和多频算法必须保留一对多，并在计频时对 `work_order_id` 去重。

## 3. 目标数据模型

### 3.1 WorkOrder

新增或明确：

- `import_batch_id`；
- `external_work_order_number`；
- `raw_title`、`raw_content`，不可变；
- `reported_at`；
- `reported_at_source`；
- `reported_at_parser_version`；
- `imported_at`；
- `source_tags`，只保存标题/渠道事实；
- `raw_payload_hash`。

禁止把 `created_at/imported_at` 继续标注为接收时间。

### 3.2 EventInstance V3

每个事项至少保存：

- `work_order_id`；
- `pipeline_version`；
- `current_problem`；
- `current_request`；
- `classification_node_id`；
- `classification_source`：`source_code | model | human`；
- `classification_confidence` 和歧义状态；
- `focal_object_mentions`；
- `responsible_party_mentions`；
- `location_mentions`；
- `occurrence_interval`；
- `history_context`；
- `previous_work_order_references`；
- 字段级 `evidence_spans`；
- `unknown_fields`；
- Provider、模型、prompt、schema、知识快照版本。

标准分类绑定在 Event Instance，而不是 Work Order。工单列表上的“诉求事项分类”是当前有效事项的聚合投影。

### 3.3 AnalysisScope 与 Job

任务创建时冻结：

- 导入批次；
- 成功工单的稳定 ID 集合或内容指纹；
- `target_work_order_count`；
- pipeline version；
- taxonomy version；
- Provider Profile 快照；
- Execution Policy 快照。

任务可分块、断点恢复和幂等重跑，但 target scope 不可变化。

### 3.4 关系证据和聚类

需要持久化：

- 对象别名 assertion 及来源；
- 候选召回路线和分数；
- Same Event 判定及双方证据；
- 聚类成员和聚类版本；
- 高频窗口、不同工单数和状态；
- 共识组名所使用的事实。

## 4. Reported At 的唯一解析顺序

`ReportedAtResolver` 按固定优先级执行：

1. 导入文件中经字段合同确认的正式受理/反映时间；
2. 经来源系统格式合同验证的工单号日期解析器；
3. 明确 `unknown`。

规则：

- 工单号解析是来源适配器，不是为 `250331` 写的案例判断；
- 解析器必须覆盖合法、非法、短号、跨年、世纪边界和空值测试；
- 结果保存 `source` 和 `parser_version`；
- 未经官方或数据合同确认，不得从工单号猜日期；
- 历史回复中的日期不能成为当前工单 `reported_at`；
- `occurrence_time` 不能替代 `reported_at` 计算三天三单；
- `imported_at` 只表示进入本系统的时间。

五张美涂士工单的 2025-03-31 必须来自上述通用来源合同。

## 5. 版本与投影

新链路使用不可变版本组合，例如：

```text
understanding.v3
classification.db44t2479-2024.v1
object-resolution.v2
same-event.v2
frequency-policy.v2
cluster.v2
```

每条结果都可追溯到原文哈希、导入批次、taxonomy、provider、模型、prompt、schema、候选策略、同事件策略和知识快照。

旧 V2 数据只读保留；页面默认读取 active pipeline projection。不得把新结果覆盖到旧版本行，也不得把不同 pipeline 的边和聚类混合。

## 6. 人工纠正

人工纠正是独立、不可变、可审计记录：

- 分类确认/纠正；
- 对象别名确认/否决；
- 同事件确认/否决；
- 聚类合并/拆分；
- 处置记录。

模型重跑应用纠正投影，但不能覆盖操作者、时间、理由和原始纠正内容。

## 7. 数据库迁移原则

1. 所有 schema 变更使用 Alembic。
2. 先新增可空字段和新表，再通过新 pipeline 回放产生数据。
3. 不从旧 `imported_at` 反推 `reported_at`。
4. 不删除旧事项、旧边、旧组和人工审计记录。
5. active projection 切换必须发生在 V3 验收通过后。
6. 回滚只切回旧 projection，不改写原始工单。
7. 需要为 taxonomy node、reported_at、pipeline version、work_order_id 和 cluster membership 建立匹配查询模式的索引。

## 8. 数据层退出条件

- 100 张工单和 103 个事项可同时正确查询；
- 五张目标工单拥有有来源的 `reported_at=2025-03-31`；
- 标准分类精确绑定到 Event Instance；
- raw text 哈希在重跑前后不变；
- 人工纠正在模型重跑后仍存在；
- 旧版本仍可审计，当前页面只投影 active version；
- 频次可按不同 Work Order 去重计算。
