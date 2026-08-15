# 09｜测试矩阵、Gold Set 与真实验收

## 1. 测试原则

- 测试证明通用合同，不给生产路径提供静态结果。
- Test Provider 必须显式命名且只存在于测试注入。
- 失败测试不能删除或 skip 来换取绿灯。
- 质量指标必须来自命名、版本化 Gold Set。
- 原始政府数据不进 Git；仓库保存允许的稳定标识、关系标注、哈希和脱敏夹具。

## 2. 附录 A 与标准分类

必须覆盖：

- 14 个一级、99 个二级、515 条三级记录；
- 不同三级印刷代码 514 个；
- 唯一重码 `090499` 恰好两条不同父路径；
- 13 条空三级名称保真及显示名继承；
- `040201`、`080508`、`100401` 精确名称和父路径；
- 孤儿节点、未知父级、未声明重码导致激活失败；
- 按 source code 确定性绑定；
- 仅传 `090499` 返回歧义，不默认第一条；
- tree、facets、列表和导出使用同一 taxonomy version；
- AI 输出自由文本或不存在 node_id 时被 Validator 拒绝。

## 3. 工单、时间与不可变性

必须覆盖：

- import mapping、畸形行、局部继续和幂等；
- raw title/content 和哈希在重跑后不变；
- 正式受理时间列优先；
- 合法、非法、空、短号、跨年工单号解析；
- imported_at 不会变成 reported_at；
- 历史回复日期不污染当前受理/事发时间；
- unknown 日期保持 unknown；
- 100 Work Order 可产生 103 Event Instance；
- 第 89/90 行保持 2/3 个事项；
- 高频计数对同一 Work Order 去重；
- 人工纠正经过模型重跑仍保留。

## 4. Understanding 与分类

必须覆盖：

- 当前投诉、当前诉求、历史背景、部门回复分段；
- 长历史回复 + 短当前诉求；
- 当前项目锚点不被历史文本覆盖；
- 字段 evidence span 存在且来自正确分段；
- 无证据实体、地点和日期不落成确定事实；
- 一张工单多个独立问题拆分；
- 同一问题多表达不重复拆分；
- 来源代码路径不调用分类模型；
- 无代码路径只能返回 active taxonomy node；
- ambiguous/unresolved 不会自动塞“其他”；
- 本地和云端执行同一 schema/validator。

## 5. 对象归一、候选与 Same Event

必须覆盖：

- 一张工单多个 mention 批量解析；
- 项目、地点、组织、品牌、道路角色区分；
- 项目别名正例；
- 共享短词但对象不同负例；
- 同分类但不同项目负例；
- 相似文本但不同地点负例；
- unknown entity/location 不幻觉；
- CandidateGenerator 每条召回路线和去重；
- Gold Set Candidate Recall@K；
- missing focal object 不得正向；
- 一方无地点时不得无证据 `same_location=true`；
- SameEvent true 字段均可追到双方证据；
- 聚类组级一致性；
- 共识命名，不取最长摘要；
- correction survives rerun。

## 6. 高频规则

边界测试至少包括：

| 日期分布（不同工单） | 预期 |
|---|---|
| 同一天 3 张 | `high_frequency` |
| 同一天 5 张 | `high_frequency` |
| 第 1/2/3 天各 1 张 | `high_frequency` |
| 第 1/2/4 天各 1 张 | `not_reached` |
| 3 个事项来自同一工单 | 只计 1 单 |
| 2 张有日期、1 张无日期 | 按合同判 `insufficient_date_evidence`，不能猜 |
| 聚类拆分后剩 2 张 | 重算为 `not_reached` |
| 人工补正合法 reported_at 后达到 3 张 | 重算为 `high_frequency` |

数据库、API 和前端枚举中都要断言不存在 `low_frequency`。

## 7. Provider 和任务

必须覆盖：

- 请求体不存在 max count；
- scope 等于批次全部成功工单；
- 大批次内部按 chunk 执行但最终不截断；
- 本地和云端都是合法 profile；
- 用户任务前可切换、任务创建后快照锁定；
- 并发任务使用不同 profile 时互不污染；
- local 选择真实提交 local profile_id；
- local 验证真实执行 LLM、Embedding、分类、SameEvent 和最小投影；
- local smoke 的调用记录不存在 cloud；
- cloud 失败不走 local，local 失败不走 cloud；
- profile validate 不含政府数据；
- API Key 和敏感 Base URL 不返回前端；
- job retry/resume/idempotency；
- partial failure 不返回全量成功。

## 8. API、统计与前端

后端：

- overview 和 list 使用同一过滤 scope；
- analysis counts 之和等于 work_order_total；
- 100 工单、103 事项、当前页 20 分开；
- 分类 facets 按完整附录 A 节点和不同工单数；
- 分类后代聚合正确；
- 090499 两条路径可独立筛选；
- reported_at/imported_at 字段不混用；
- 静态 overview 路由不被动态 ID 吞掉。

前端：

- 不存在研判数量输入；
- Provider 卡、验证、选择和锁定状态正确；
- 100/103 固定说明长期可见；
- 分析状态、诉求事项分类、来源标记是三个控件；
- 分类树完整来自后端；
- 当前页不冒充全量统计；
- 导入时间不标为受理时间；
- Dashboard DOM 不存在质量指标板块；
- 处置表单 DOM 和请求中不存在附件编号；
- 页面不存在“低频事件”；
- 达门槛的美涂士组显示高频；
- 后端错误不会被轮询吞掉；
- 历史附件可只读显示。

## 9. Demo Gold Set v1

### 9.1 美涂士正例

以下五张必须属于同一组：

- `250331144260109-01`；
- `250331149120109-01`；
- `250331160700109-01`；
- `250331163110109-01`；
- `250331166680109-01`。

验收：

- 五张均成功理解；
- 四种项目说法归一；
- 分类均为 `080508`；
- reported_at 均为 2025-03-31 且 provenance 合法；
- 一个目标组，`distinct_work_order_count=5`；
- `frequency_status=high_frequency`；
- 组名来自共识；
- 页面能解释为什么关联。

### 9.2 欠薪强负例

世贸国风滨江工地欠薪与五张美涂士分别为 `not_same`，主要依据是焦点项目不同。不能因为同属 `080508` 合并。

### 9.3 三个“美的”强负例

- 美的集团冰箱质量 -> `100401`；
- 美的第五工业区机器噪音 -> `040201`；
- 美的大道项目拖欠工资 -> `080508`。

三者必须实际经过 Hard Negative 判定，验证完整对象、分类和地点差异；共享短词不能形成 alias 或同事件。

### 9.4 一张工单多事项

第 89、90 行继续输出 2/3 个事项，总体保持 100/103。页面和多频计数不得为数字整齐牺牲拆分能力。

## 10. 性能基准

### 10.1 测量维度

记录：

- 数据集、pipeline、taxonomy、provider 和模型版本；
- 硬件、量化、上下文、batch 和各阶段并发；
- 总吞吐、P50/P95；
- 各阶段耗时；
- 请求数、token、429、重试；
- 候选数和 SameEvent 调用量；
- 峰值 RAM/VRAM。

### 10.2 云端验收

100 条预热后连续三次：P50 ≤ 5 分钟、每次 ≤ 7 分钟，且 Gold Set 不下降。当前 745 条匹配边应在保持正例 Candidate Recall=100% 的前提下显著收敛，目标 SameEvent LLM pair ≤ 200。

### 10.3 本地验收

真实最小完整 E2E smoke 通过；峰值 RAM/VRAM 不超过单请求基线 110%；不要求本轮用本地完整跑 100 条，但系统不能设置本地批次条数上限。

## 11. 真实回放记录

最终报告必须保存：

- 原始批次行数和哈希；
- 成功/失败工单；
- 100/103；
- Gold Set 每项结果；
- taxonomy 完整性；
- local smoke 调用证据；
- cloud 100 条性能三次结果；
- Playwright 演讲流程截图/报告；
- 所有失败和重试，不删减不美化。

## 12. 仓库必跑检查

按仓库实际脚本执行；没有聚合脚本时至少执行：

```text
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright backend
uv run pytest -q
pnpm install --frozen-lockfile
pnpm lint
pnpm test --run
pnpm build
Playwright 主流程
```

实际命令输出摘要写入 `docs/CURRENT_STATE.md`，不能只写“测试通过”。
