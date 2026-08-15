# PRODUCT_SCOPE.md

## 当前冻结产品方向

这是“12345 多频工单智能研判”，不是通用 RAG 问答助手。

主闭环：

`Excel/CSV导入 → 工单理解 → 实体归一 → 同事件识别 → 多频事件组 → 可核查依据 → 纠错/业务处理 → 导出`

### 最新决策
- AI 直接输出多频事件结果，不设置强制人工复核队列。
- 保留人工纠错和操作留痕；当前 Demo 已提供 `remove_member` / `confirm_member`，merge/split 仍需单独的领域规则与验收后再做。
- 原始工单永远与 AI 派生理解分离。
- 多频次数按不同原始工单（distinct WorkOrder）计算，不按 AI 拆出的 EventInstance 数计算；一张工单即使包含多个真实问题，也不能单独形成多频事件。
- 同一工单内的多个真实问题可以保留为多个 EventInstance，但它们不进入跨工单 retrieval / SameEvent / cluster；部门回复、历史处置和当前请求只是事件上下文，不应被拆成虚假独立事件。
- 同主体不同事件不能合并。
- 当前比赛/Demo 路径显式采用 cloud-first：理解、embedding、SameEventMatcher 均可走已配置的 remote OpenAI-compatible provider；未显式设置 remote 时，代码安全默认仍是 local，绝不自动云回退。
- Demo Core 只处理从真实 PostgreSQL 动态选择的小样本，不把 128,278 条全量 LLM 分析伪装成完成；每条远程结果必须保留 provider、model、config hash、pipeline/schema trace。
- 支持 Excel/CSV。
- 支持事件业务处理状态/过程/结果。
- 多频事件详情必须可核查成员工单、SameEvent evidence、AI trace、处理历史和人工纠错；处理记录与纠错通过 backend API 写入既有表并留下审计。
- 支持多频事件 CSV 导出，导出只读派生投影，不改写原始工单。
- 支持删除单条/批量/整个导入批次，并明确级联与审计。
- 人文关怀不做心理诊断；个人 Care Signal 只有存在合规、稳定诉求人标识时才可实现。

### 当前四个核心页面
1. 数据导入
2. 工单中心
3. 多频事件
4. 事件详情/研判

可以在同一信息架构中增加处理记录/社区提示区，但不要为了比赛变成复杂大屏。

### 不做
- 通用知识库问答
- 自动行政认定
- 自动结案/自动派单作为比赛主流程
- 个人心理诊断/画像
- 把云端模型调用写死到业务 handler；商业供应商必须隐藏在 `LLMProvider` / `EmbeddingProvider` / `SameEventMatcher` 之后

### 原“20条痛点”
如产品负责人提供原文，存入 `docs/PAIN_POINTS_LOCKED.md`，逐字冻结。此文件不重新发明那20条表述。
