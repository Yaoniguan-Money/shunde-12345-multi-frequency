# 05｜同事件、聚类与三天三单高频规则

## 1. 目标定义

系统不是找“相似文字”，而是判断多个 AI 研判事项是否指向同一现实集中问题。

同事件最低语义：

- 同一焦点现实对象；
- 同一或明确兼容的诉求事项分类；
- 受理时间窗口兼容；
- 无地点、责任对象、问题类型或处理链硬冲突。

## 2. CandidateGenerator：混合且有界

候选集合由以下通道并集产生：

1. canonical focal object 相同；
2. 项目/组织别名归一相同；
3. 标准分类 + 行政区域 + `reported_at` 窗口兼容；
4. 引用同一历史工单号或处置链；
5. 结构化专名和关键词检索；
6. normalized summary Embedding top-k。

每条候选保存：

- `retrieval_routes`；
- 各通道分数；
- 结构化锚点；
- 召回版本；
- 被截断或保留的原因。

限制的是每个事项候选数和模型调用并发，不是导入批次工单总数。禁止全库 O(N²) 两两比较。

## 3. 进入模型前的确定性约束

以下情况可直接排除，不消耗 SameEvent LLM：

- 双方焦点对象均已确定且不同；
- 双方具体地点均已确定且冲突；
- 标准分类明确不兼容；
- 时间窗明确不兼容；
- 仅共享通用问题词或短品牌词；
- 人工已有不可变的 not-same 纠正。

以下强证据可以提高候选优先级，但最终仍通过统一判定合同：

- canonical focal object 相同；
- 同一处置链或历史工单引用；
- 同项目别名 + 同标准分类 + 三日窗口。

## 4. SameEventJudgeV2

结构化输出至少包含：

```text
same_focal_object
same_responsible_party
same_classification
report_window_compatible
same_handling_chain
same_location
claimant_variation_compatible
contradictions[]
unknowns[]
final_decision: same | not_same | ambiguous
confidence
evidence_refs[]
```

正向结论必须满足：

- 焦点对象已确认相同；
- 标准分类相同或由受控规则声明兼容；
- `reported_at` 时间兼容，或存在同一处理链强引用；
- 每个 true 字段均引用双方证据；
- 不存在硬冲突。

关键锚点缺失时返回 `ambiguous`，不得因为“都是欠薪”猜成 same。`ambiguous` 不进入自动聚类正向边。

## 5. ClusterAssembler

聚类规则：

- 只消费 V2 判定的有效正向边和人工确认边；
- pipeline、taxonomy、same-event policy 版本一致；
- 新成员加入后不得与组内强共识冲突；
- 成员工单数使用 `COUNT(DISTINCT work_order_id)`；
- 一张工单中的多个事项不能把频次抬高；
- 人工拆分/合并通过独立审计投影，不覆盖模型边。

不能只用传递闭包把 A≈B、B≈C 自动推成 A≈C。组件形成后必须执行组级一致性检查。

## 6. ClusterNarrativeBuilder

组名和“为什么关联”从组内共识生成：

- canonical focal object；
- 标准分类；
- 受理时间窗口；
- 可选行政区域；
- 项目别名证据。

禁止取最长成员摘要作为组名。只有通用链路确认后，才可以自然生成“某项目欠薪集中反映”一类标题。

详情页必须展示：

- 哪些叫法被归为同一项目；
- 哪些工单提供对象、分类、地点和时间证据；
- 哪些字段仍未知；
- 哪些候选被排除及主要冲突；
- 模型、taxonomy、判定和聚类版本。

## 7. 高频规则：唯一口径

### 7.1 业务定义

同一聚类中，只要存在任意连续 3 个自然日窗口，包含 3 张及以上不同工单，就必须标记为高频。

这里锁定的是“3 单及以上”，不是“必须超过 3 单”。美涂士同一天 5 张显然是高频。

### 7.2 算法

```text
dates = 每个不同 work_order_id 的有效 reported_at 日期
sort(dates)
for each start_date D:
    count distinct work_order_id where D <= reported_date <= D + 2 days
    if count >= 3:
        status = high_frequency
        persist winning window and members
```

同一天的 5 张工单计 5 单；一张工单拆出 3 个事项仍只计 1 单。

### 7.3 状态机

只允许：

- `high_frequency`：证据证明达到门槛；
- `not_reached`：有效日期足以计算，但所有三日窗口都不足 3 张；
- `insufficient_date_evidence`：日期缺失，不能可靠判断。

不定义 `low_frequency`。前端、API、数据库枚举和筛选中都不得出现“低频事件”。

### 7.4 重算触发

以下变化必须用同一 policy version 重算：

- 聚类新增/移除成员；
- `reported_at` 经合法来源纠正；
- 人工合并/拆分；
- active pipeline 切换；
- same-event 纠正生效。

满足门槛后，任何页面都不能因为分页或事项数口径显示 `not_reached`。

## 8. 美涂士正例

五张工单：

- `250331144260109-01`；
- `250331149120109-01`；
- `250331160700109-01`；
- `250331163110109-01`；
- `250331166680109-01`。

目标结果：

- canonical focal object 相同；
- 标准分类均为 `080508`；
- `reported_at` 均为 2025-03-31；
- 一个组包含 5 张不同工单；
- `frequency_status=high_frequency`；
- winning window 为 2025-03-31 至 2025-04-02，实际成员都在首日；
- 页面显示项目别名和判断依据。

## 9. 强负例

- 世贸国风滨江工地欠薪与美涂士分类同为 `080508`，但焦点项目不同，必须 `not_same`。
- 美的集团冰箱质量、美的第五工业区噪音、美的大道项目欠薪共享短词“美的”，但对象、分类和地点不同，必须保持分离。
- 负例必须实际进入受控候选/判定测试，不能仅因偶然未召回而算通过。

## 10. 退出条件

- Gold Set 正例 Candidate Recall=100%；
- 五张美涂士只有一个目标组，错误欠薪项目不进入；
- 三个“美的”有可追踪负向理由；
- 高频按不同工单和 `reported_at` 正确计算；
- 达到三天三单时绝不显示“低频”或“未达到”；
- 没有 O(N²) 全库比较，Embedding 不直接建边；
- 组名来自共识而非最长摘要。
