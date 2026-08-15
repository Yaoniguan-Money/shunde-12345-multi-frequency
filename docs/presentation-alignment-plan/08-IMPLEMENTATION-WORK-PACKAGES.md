# 08｜实施工作包、依赖与代码落点

本文件定义实施顺序，不代表已经执行。每个工作包只有在测试和退出条件通过后才能进入下一阶段。

## WP0｜冻结术语、ADR 和接口

目标：先消除“类型、事件、时间、频次、模型切换”的口径冲突。

更新：

- `docs/PRODUCT_SCOPE.md`：全批次研判、任务前 provider 选择、完整附录 A；
- `docs/ARCHITECTURE.md`：新数据流和深模块；
- `docs/DECISIONS.md`：取代 1—300、remote-only、occurrence-date 高频等旧决策；
- `docs/TRAE_HANDOFF.md`：锁定前端 API 与文案；
- `docs/CURRENT_STATE.md`：未完成项保持 PLANNED/PARTIAL。

退出：字段、枚举、时间、高频和 Same Event 定义全部评审通过。

## WP1｜附录 A 目录与迁移

必读：[01-DB44-TAXONOMY.md](01-DB44-TAXONOMY.md)、[02-DOMAIN-DATA-TIME.md](02-DOMAIN-DATA-TIME.md)。

主要位置：

- `backend/app/domain/taxonomy.py`；
- `backend/app/domain/ports/taxonomy.py`；
- `backend/app/infrastructure/taxonomy/`；
- `backend/app/infrastructure/db/models/`；
- `backend/app/infrastructure/db/taxonomy.py`；
- Alembic migration；
- 受控 taxonomy seed/resource。

实施：

- 建立 TaxonomyVersion/Node；
- 导入 14/99/515；
- 保留 `090499` 两条和 13 条空三级名称；
- 激活完整性校验；
- 建立代码/路径解析器；
- 增加 tree 和 stats repository。

退出：目录完整性和关键代码测试通过，前端无需自带分类常量。

## WP2｜领域数据、Reported At 与 AnalysisScope

主要位置：

- `backend/app/domain/analysis.py`；
- `backend/app/domain/analysis_jobs.py`；
- `backend/app/domain/imports.py`；
- `backend/app/infrastructure/imports.py`；
- `backend/app/infrastructure/db/models/work_orders.py`；
- `backend/app/infrastructure/db/models/events.py`；
- `backend/app/infrastructure/db/models/analysis.py`；
- Alembic migration。

实施：

- WorkOrder 添加 reported/imported 时间语义和 provenance；
- EventFact V3、分类节点和 evidence；
- 任务冻结全部成功工单；
- 删除产品级 max count；
- 幂等、checkpoint、resume；
- 旧 pipeline 只读保留。

退出：五张工单日期有合法来源；任意 N 条形成 N 条 scope；100/103 可查询。

## WP3｜理解、事项拆分与标准分类

必读：[03-UNDERSTANDING-CLASSIFICATION.md](03-UNDERSTANDING-CLASSIFICATION.md)。

主要位置：

- `backend/app/domain/services/segmentation.py`；
- `backend/app/schemas/ai.py`；
- `backend/app/application/services/understanding.py`；
- 新 classification application/domain service；
- `backend/app/infrastructure/ai/local.py`；
- `backend/app/infrastructure/ai/openai_compatible.py`；
- `backend/app/infrastructure/ai/remote.py`。

实施：

- 当前投诉/历史/回复/诉求分段；
- EventFact[] 和字段 evidence；
- source code 确定性分类；
- 无代码时 taxonomy-constrained 分类；
- 空/歧义状态；
- 多事项回归；
- 缓存和版本。

退出：美涂士五张均保留项目和 `080508`；第 89/90 行仍为 2/3 事项。

## WP4｜Reality Object、候选、Same Event 与高频

必读：[05-SAME-EVENT-FREQUENCY.md](05-SAME-EVENT-FREQUENCY.md)。

主要位置：

- `backend/app/domain/ports/gazetteer.py` 并逐步抽出 object resolver；
- `backend/app/infrastructure/knowledge/`；
- `backend/app/infrastructure/db/retrieval.py`；
- `backend/app/infrastructure/ai/same_event.py`；
- `backend/app/application/services/event_graph.py`；
- `backend/app/domain/services/clustering.py`；
- `backend/app/domain/services/frequency.py`；
- 对应 DB models/repositories。

实施：

- 项目/机构/地点/产品/道路分型；
- 批次别名候选和可审计 assertion；
- 混合有界候选；
- SameEventJudgeV2 和硬锚点门槛；
- 组级一致性、共识命名；
- `reported_at` 三日窗口、不同工单计数；
- 移除 `low_frequency` 枚举。

退出：美涂士五张成组且为高频；世贸欠薪和三个“美的”负例通过。

## WP5｜Provider 按任务选择与性能

必读：[04-PROVIDER-TASK-PERFORMANCE.md](04-PROVIDER-TASK-PERFORMANCE.md)。

主要位置：

- `backend/app/infrastructure/ai/config.py`；
- `backend/app/infrastructure/ai/factory.py`；
- `backend/app/infrastructure/ai/openai_compatible.py`；
- `backend/app/application/services/analysis_jobs.py`；
- `backend/app/application/services/indexing.py`；
- `backend/app/application/services/event_graph.py`；
- `backend/app/infrastructure/health.py`；
- `backend/app/api/analysis.py`；
- 新 provider profile API；
- `backend/app/config.py`。

实施顺序：

1. ProviderProfileRegistry 和 per-job snapshot；
2. profile list/validate；
3. local/cloud 独立 Execution Policy；
4. persistent HTTP client；
5. 批量预载和批量写；
6. 候选调用量收敛；
7. 阶段流水化；
8. 云端有界并发基准。

退出：本地最小完整链路真实通过；云端 100 条达到性能验收；无跨 provider fallback。

## WP6｜API、统计和分类筛选

必读：[06-API-PROJECTIONS.md](06-API-PROJECTIONS.md)。

主要位置：

- `backend/app/domain/catalog.py`；
- `backend/app/domain/ports/catalog.py`；
- `backend/app/application/services/catalog.py`；
- `backend/app/infrastructure/db/catalog.py`；
- `backend/app/schemas/catalog.py`；
- `backend/app/api/catalog.py`；
- taxonomy/provider schemas 和 routes；
- `backend/app/domain/title_tags.py` 仅保留 source tag 语义。

实施：

- overview/facets；
- 全部筛选后端化；
- taxonomy tree；
- 100/103/当前页数字分离；
- 分类、分析状态、来源标签分离；
- 事件频次状态接口；
- 明确错误合同。

退出：overview 与列表同 scope，状态总和一致，附录 A 全量可筛选。

## WP7｜前端对齐

必读：[07-FRONTEND-UX.md](07-FRONTEND-UX.md)。

主要位置：

- `frontend/src/types/api.ts`；
- `frontend/src/api/analysis.ts`；
- `frontend/src/api/catalog.ts`；
- `frontend/src/api/health.ts`；
- taxonomy/provider API 模块；
- `ImportsPage.tsx`；
- `WorkOrdersPage.tsx`；
- `DashboardPage.tsx`；
- `EventsPage.tsx` / `EventsListPage.tsx`；
- `ClusterDetailPage.tsx`；
- `WorkOrderDetailPage.tsx`；
- 对应测试。

实施：

- 删除数量输入；
- Provider 卡和真实验证；
- 全量统计和 100/103 说明；
- 完整分类级联筛选；
- 删除质量板块；
- 删除附件编号；
- 高频状态无低频；
- 详情证据和别名映射。

退出：演讲稿流程无需案例专页即可走通。

## WP8｜真实回放、评测与交付

必读：[09-TESTS-ACCEPTANCE.md](09-TESTS-ACCEPTANCE.md)、[10-NO-DEGRADATION-AND-DOD.md](10-NO-DEGRADATION-AND-DOD.md)。

步骤：

1. 隔离数据库导入真实 100 条；
2. 核对行数、哈希和幂等；
3. 真实验证本地最小完整链路；
4. 选择云端千问运行完整 100 条；
5. 跑 Demo Gold Set 和 Hard Negatives；
6. 验证 100/103、分类、日期、聚类和高频；
7. 跑性能基准；
8. 用 Playwright 按演讲稿走 UI；
9. 更新 CURRENT_STATE、DECISIONS、ARCHITECTURE、TRAE_HANDOFF；
10. 运行全量检查后再提交。

## 并行规则

WP1 和 Provider Registry 的接口设计可并行；WP3 必须等 WP1/WP2 的 schema 冻结；WP4 必须消费 WP3 的 V3 facts；WP6 在领域 schema 冻结后进行；WP7 只能依赖真实 API 契约，不得先用静态假响应完成页面。
