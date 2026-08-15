# 06｜API、全量统计与筛选投影

## 1. 契约原则

- API 路由只解析参数和返回 schema，业务逻辑在 application/domain。
- 所有列表与概览使用同一 ScopeFilter。
- 全量统计由数据库聚合，前端不能从当前页推算。
- taxonomy、pipeline 和 provider 版本均显式返回。
- 错误使用明确状态和结构化原因，不返回假成功。

## 2. Provider 接口

### 2.1 `GET /ai/provider-profiles`

返回本地和云端可选 Profile：

```json
{
  "items": [
    {
      "profile_id": "cloud-qwen",
      "deployment_kind": "cloud",
      "display_name": "云端模型（千问，已适配）",
      "configured": true,
      "validation_status": "validated",
      "last_validated_at": "...",
      "model_display_name": "...",
      "service_description": "已脱敏"
    }
  ]
}
```

不得返回 API Key、完整认证头或可由浏览器覆盖的 Base URL。

### 2.2 `POST /ai/provider-profiles/{profile_id}/validate`

执行真实的有界完整链路验证，返回每个阶段的：

- `status`；
- `latency_ms`；
- `model_id`；
- `schema_version`；
- 脱敏错误；
- 实际 provider 调用证据。

验证不创建正式业务任务，也不使用政府原文。

## 3. 研判任务接口

### 3.1 创建

`POST /analysis-jobs`

```json
{
  "import_batch_id": "uuid",
  "provider_profile_id": "cloud-qwen"
}
```

请求中不存在 `max_work_orders`、`selection_mode` 或前端并发参数。

响应至少包含：

- `job_id`；
- `status: queued | running | completed | completed_with_failures | failed`；
- `target_work_order_count`；
- `processed_work_order_count`；
- `failed_work_order_count`；
- `produced_event_instance_count`；
- `provider_profile_snapshot`；
- `execution_policy_snapshot`；
- `pipeline_version`；
- `taxonomy_version`；
- checkpoint 和错误摘要。

### 3.2 幂等与恢复

幂等键至少由下列内容构成：

- import batch 内容指纹；
- pipeline version；
- taxonomy version；
- provider profile 配置版本。

恢复接口必须继续同一 AnalysisScope，不得重新选择部分工单或自动换模型。

## 4. 标准分类目录接口

### 4.1 `GET /taxonomies/active`

返回 active version 的基本信息、PDF/资源哈希和完整性统计。

### 4.2 `GET /taxonomies/{version}/tree`

返回 14/99/515 的完整树。每个节点包含：

- `node_id`；
- `level`；
- `printed_code`；
- `printed_name`；
- `display_name`；
- `display_name_source`；
- `parent_node_id`；
- `full_path`；
- `remark`；
- `source_anomaly`。

前端不得自己补齐或维护分类常量。

### 4.3 代码解析

按 `classification_node_id` 查询必须唯一。按 `printed_code=090499` 查询返回两条完整父路径和 `ambiguous=true`，不能默认选第一条。

## 5. 工单列表与概览

### 5.1 统一 ScopeFilter

列表和概览共同接受：

- `import_batch_id`；
- `query`；
- `analysis_outcome`；
- `classification_node_id`；
- `include_descendants`；
- `source_tag`；
- `urgency`；
- `frequency_status`；
- `pipeline_version`，默认 active。

所有筛选在后端执行，搜索和筛选不能只作用于当前页。

### 5.2 `GET /work-orders/overview`

返回：

```text
scope
work_order_total
analysis_outcome_counts
event_instance_total
multi_frequency_cluster_total
frequency_status_counts
classification_facets
source_tag_facets
unknown_classification_work_order_count
```

约束：

- `analysis_outcome_counts` 之和等于 `work_order_total`；
- facets 默认计不同工单数；
- 若同时返回事项数，字段名必须带 `event_instance_count`；
- 当前页数量不属于 overview；
- 分类 facets 带 node_id、代码、名称、路径和后代聚合口径。

### 5.3 `GET /work-orders`

分页项至少包含：

- 工单号和标题；
- `classifications[]`，来自当前有效事项；
- `source_tags[]`；
- `analysis_outcome`；
- `event_instance_count`；
- `multi_frequency_membership_count`；
- `frequency_statuses[]`；
- `reported_at` 和来源；
- `imported_at`。

静态 `/overview` 路由注册在动态 `/{work_order_id}` 之前，避免路径冲突。

## 6. 分析状态与分类不可混用

分析状态稳定枚举：

- `unprocessed`；
- `analyzed_no_event`；
- `analyzed`；
- `failed`。

分类状态另行表达：

- `resolved`；
- `ambiguous`；
- `unresolved`；
- `human_corrected`。

标准分类筛选只读取 Classification Node；“急、城管、小程序自助”等只属于 `source_tags`。

## 7. 事件与高频接口

`GET /event-clusters` 支持：

- `frequency_status=high_frequency | not_reached | insufficient_date_evidence`；
- taxonomy node 及后代；
- 受理时间范围；
- canonical focal object 搜索；
- 分页和排序。

每个聚类返回：

- `distinct_work_order_count`；
- `event_instance_count`；
- `frequency_status`；
- winning three-day window；
- canonical object；
- classification path；
- report window；
- cluster narrative；
- active versions。

状态中不允许 `low_frequency`。

详情接口还要返回：

- 成员工单和事项；
- 别名映射；
- SameEvent 边和证据；
- 冲突与未知字段；
- 高频计数所使用的不同工单；
- 人工纠正投影和审计记录。

## 8. 分类与关系纠正接口

纠正请求必须记录：

- 目标对象；
- 旧值；
- 新值；
- 操作者；
- 时间；
- 原因；
- 当前版本。

分类纠正提交 `classification_node_id`。同事件、聚类合并/拆分和别名纠正使用各自窄接口，不能通过直接覆盖 AI 行实现。

## 9. 附件兼容

前端新增处置请求不再发送 `attachment_references`。后端可以暂时保留历史读取字段和附件路由，避免破坏已有审计；新建接口应接受不带附件字段的明确 schema，而不是前端发送空数组假装保留功能。

## 10. 错误合同

至少区分：

- provider 未配置/未验证；
- taxonomy 未激活/不完整；
- source code 歧义；
- 模型 schema 失败；
- evidence 校验失败；
- 单工单处理失败；
- checkpoint 恢复失败；
- 速率限制和认证错误。

前端必须显示后端错误摘要；轮询不得 catch 后继续显示“处理中”。
