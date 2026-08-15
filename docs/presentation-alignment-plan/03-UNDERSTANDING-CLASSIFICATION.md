# 03｜工单理解、事项拆分与标准分类

## 1. 目标

AI 先理解群众当前在反映什么，再把每个独立事项映射到标准分类和现实焦点对象。历史回复只能作为处理背景，不能覆盖当前投诉中的项目、问题、诉求和时间。

## 2. WorkOrderUnderstandingV3

理解链路固定分为三步。

### 2.1 文本分段

把原始文本分成：

- `current_complaint`：本次群众陈述；
- `current_request`：当前明确诉求；
- `history_context`：此前投诉或背景；
- `department_reply`：部门历史答复。

每个分段保留原文起止区间和分段依据。不能只把整段文字截断后一次送入模型。

### 2.2 当前事项提取

只从 `current_complaint + current_request` 创建本次 Event Instance。历史段可以补充：

- 曾处理部门；
- 历史工单号；
- 已有答复和处理链；
- 当前投诉明确引用的背景。

历史内容不能覆盖当前焦点项目、当前问题类型和当前受理时间。

### 2.3 字段证据校验

项目、组织、地点、问题、诉求、日期等关键字段必须引用原文 evidence span。Validator 检查：

- evidence 是否真正在原文；
- evidence 是否来自允许的分段；
- 字段与 evidence 是否语义一致；
- 历史日期是否污染当前字段；
- 关键字段是否被模型凭空补全。

结构合法但关键锚点缺失时只允许一次有界结构化修复。修复仍失败则记录明确失败/待重判，不得以“已分析”进入聚类。

## 3. 多事项拆分

模型输出是 `EventFact[]`，不是单个摘要。一张工单同时反映不同现实问题时必须拆分，例如噪音和占道经营属于两个事项。

拆分规则：

- 现实焦点对象不同，通常拆分；
- 问题类型和处置路径独立，拆分；
- 同一对象、同一问题的多个表达不重复拆分；
- 历史回复中的旧问题不创建为本次事项；
- 每个事项拥有独立分类、对象、地点、诉求和证据。

现有第 89、90 行分别产生 2、3 个事项的能力必须回归通过。

## 4. 标准分类器

### 4.1 确定性代码路径

来源存在有效标准代码时：

```text
source code
  -> normalize
  -> taxonomy lookup
  -> hierarchy validation
  -> classification_node_id
```

这一分支不调用模型。代码、名称和完整路径由 active taxonomy 唯一投影。

### 4.2 无代码内容分类路径

来源没有代码时：

```text
current event facts
  -> deterministic candidate narrowing
  -> bounded provider classification
  -> classification_node_id only
  -> taxonomy validator
```

候选缩小可使用：

- 标准备注中的领域词和对象类型；
- 一级/二级路由器；
- 结构化问题和诉求；
- 受控检索索引；
- 本地或云端 Provider 的结构化判断。

模型输出不能直接携带自创中文类型。最终存储的名称和父路径始终来自 taxonomy。

### 4.3 分类输出合同

```text
classification_node_id
candidate_node_ids
decision: resolved | ambiguous | unresolved
confidence
evidence_refs
reason
provider_profile
taxonomy_version
```

`ambiguous` 和 `unresolved` 是真实业务状态，不得自动塞进“其他”伪装成功；只有文本确实符合标准“其他”节点时才能选择该节点。

## 5. 现实对象角色

同一工单中的 mention 必须批量解析，并区分：

- `focal_project`：群众投诉焦点项目；
- `place`：地址或区域；
- `responsible_organization`：责任单位；
- `construction_organization`：施工单位；
- `developer/owner`：建设或开发单位；
- `product_or_brand`：产品或品牌；
- `road/facility`：道路或公共设施。

不能把所有专名都塞进地点词典。RealityObjectResolver 按对象类型调用 Project、Organization、Place、Product/Brand、Road 等适配器。

## 6. 别名归一

同一批次内的对象别名候选结合：

- 对象类型；
- 高区分度核心名称；
- 地址和行政区域；
- 建设/施工/责任单位关系；
- 问题上下文；
- 明确冲突。

“美涂士智能总部”“美涂士二期工程”“美涂士全球生态智能总部二期项目”“广东美涂士全球生态智能总部”应通过通用项目归一形成同一 Focal Object。

共享“美的”两个字不足以建立别名。产品、工业区和道路项目的对象类型、完整名称、地点与标准分类均不同。

所有 alias assertion 保存来源、证据、版本和状态。模型一次判断不能被静默写成永久知识。

## 7. 本地与云端一致合同

本地和云端必须使用：

- 同一输入 schema；
- 同一输出 schema；
- 同一 taxonomy 候选目录；
- 同一 evidence Validator；
- 同一 Gold Set；
- 同一未知/歧义语义。

不得给本地模型缩成两个类别，也不得为云端模型放开自由文本。

## 8. 缓存与版本

可缓存昂贵结果，但缓存键必须包含：

- 原文哈希和分段版本；
- taxonomy version；
- provider profile 配置版本；
- 模型、prompt、schema；
- object-resolution knowledge snapshot。

缓存命中不能跳过 schema/evidence 校验。

## 9. 退出条件

- 五张美涂士工单均抽到当前项目锚点和 `080508`；
- 长历史回复没有覆盖当前项目或日期；
- 美的冰箱、工业区噪音、道路项目欠薪分别映射 `100401`、`040201`、`080508`；
- 100 张仍可产生 103 个事项；
- 所有分类结果属于 active taxonomy；
- 无 evidence 的对象、地点和日期不落成确定事实；
- 本地和云端合同测试完全相同。
