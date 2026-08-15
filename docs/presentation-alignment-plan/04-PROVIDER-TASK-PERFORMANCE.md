# 04｜任务模型切换、本地真实链路与性能

## 1. 产品目标

每次研判任务开始前，用户可以选择：

- 本地模型；
- 云端模型（当前千问已适配）。

选择必须真正决定该任务的 LLM 和 Embedding 路径。任务运行中锁定，下一任务可重新选择。

## 2. ProviderProfileRegistry

服务端维护安全的 Provider Profile：

```text
profile_id
deployment_kind: local | cloud
display_name
llm_adapter + model_id
embedding_adapter + model_id
structured_output_capability
configured
last_validation_status
last_validated_at
redacted_service_description
configuration_version
execution_policy
```

前端只传 `profile_id`，不能传 API Key 或任意 Base URL。任务保存完整脱敏快照，避免配置变更影响运行中的任务。

业务服务只依赖 Provider 端口。千问名称只出现在 cloud profile 配置和安全展示，不进入 SameEvent、分类或聚类领域代码。

## 3. 任务前切换合同

```text
导入批次完成
  -> GET provider profiles
  -> 用户验证/选择 profile
  -> POST analysis job(profile_id)
  -> 冻结 profile + execution policy
  -> 执行全部成功工单
```

状态要求：

- `configured`：配置存在但未证明完整能力；
- `validated`：真实链路验证通过；
- `unavailable`：服务不可访问；
- `validation_failed`：能力合同失败。

只有 `validated` 的 profile 才允许创建生产研判任务。不得把“按钮可点击”当成链路已通。

## 4. Provider 验证接口

验证使用不含政府数据的极小合成样本，必须真实执行：

1. 服务连接和模型存在性；
2. LLM 结构化 EventFact 输出；
3. DB44 分类节点约束输出；
4. Embedding 输出和维度合同；
5. SameEvent 结构化判断；
6. 最小 `导入夹具 -> 理解 -> 分类 -> 向量 -> 候选 -> 判定 -> 聚类投影`；
7. 记录所有实际调用的 provider，证明没有跨 provider fallback。

本地本轮不要求完整跑 100 条，但上述最小完整链路必须真实通过。只做 `/health`、模型列表或单次 ping 不算完成。

## 5. 当前已定位的耗时来源

当前代码存在以下结构性问题：

- 一个全局 `model_concurrency` 同时控制 indexing chunk、LLM、检索和 SameEvent；
- 每个 chunk 按理解、持久化、Embedding、持久化串行推进；
- SameEvent 对每个候选 pair 重复加载左右事项；
- 单 pair 调用被包装成 `generate_batch((request,))`；
- OpenAI-compatible 调用频繁新建 `AsyncClient`，没有连接池复用；
- 边和部分结果逐条持久化；
- 当前 103 个事项产生 745 条匹配边，弱候选造成大量无价值云端判断。

所以不能只把全局并发数字调大。

## 6. Provider 专属 Execution Policy

将全局参数拆为任务快照中的阶段参数：

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

### 6.1 云端策略

- 使用持久化异步 HTTP client 和连接池；
- Understanding、Classification、Embedding、SameEvent 分别有界并发；
- 通过真实 RPM/TPM、平均 token 和 429 比例确定上限；
- 用 `8/16/24` 等梯度做基准，不把某个数字写成业务规则；
- 支持 token-aware 限流、指数退避和可观测重试；
- 对无依赖阶段做有界流水化；
- 批量加载事项、候选和证据，批量持久化结果；
- 复用结构化 prompt 前缀和 taxonomy 检索索引。

### 6.2 本地策略

- 默认保持单 LLM in-flight 或由推理服务内部 continuous batching；
- Embedding 可按内存预算小批处理；
- 不通过多个并发生成请求增加 KV Cache；
- 数据预处理、目录检索、DB I/O 可与模型推理有限重叠；
- profile 独立设置，不受 cloud 并发参数影响；
- 峰值 RAM/VRAM 超预算时该配置不通过验收，不能减少研判范围补救。

## 7. 优先提速顺序

### 7.1 减少无价值模型调用

- 标准代码存在时不调用分类模型；
- taxonomy 一级/二级先确定性缩小三级候选；
- 同一 canonical object + 分类 + 日期生成候选；
- 明确对象/地点冲突直接排除；
- Embedding 只召回，不把弱相似全送 SameEvent；
- 重用已版本化的理解、分类、Embedding 和对象解析缓存。

### 7.2 消除重复 I/O

- 一个 graph run 批量预载候选事项和证据；
- SameEvent matcher 接收已加载的 immutable facts，不逐 pair 回库；
- 批量写边、聚类成员和进度；
- OpenAI-compatible adapter 复用 client、连接和认证头。

### 7.3 阶段流水化

在不改变结果依赖的前提下，让已完成理解的 chunk 进入 Embedding，同时下一 chunk 做云端理解。边界使用有界队列和 checkpoint，不能无限创建任务。

### 7.4 最后提高云端并发

只有前述优化和基准完成后，才逐级提高云端阶段并发。遇到 429/超时要降低调度速率并明确记录，不能改走本地或跳过记录。

## 8. 性能与资源验收

### 8.1 云端 100 条

在相同数据、pipeline、taxonomy、千问模型和网络环境下：

- 预热后连续运行 3 次；
- 总耗时 P50 目标不超过 5 分钟；
- 单次不超过 7 分钟；
- 100 张全部处理，Gold Set 结果不下降；
- 记录 Understanding、Classification、Embedding、Candidate、SameEvent、Cluster 各阶段 P50/P95；
- 记录请求数、token、429、重试和候选数分布。

### 8.2 候选调用量

当前 103 个事项、745 条匹配边作为基线。目标在保持 Gold Set 正例 Candidate Recall=100% 的前提下，把需要进入 SameEvent LLM 的 pair 控制在 200 以内。若实测证明 200 不足，应基于 benchmark 调整，并记录原因，不能牺牲正例召回。

### 8.3 本地资源

- 记录单请求基线峰值 RAM 和 VRAM；
- 优化后峰值不超过基线的 110%；
- 真实最小端到端 smoke 通过；
- 不以增加并发模型副本、上下文长度或 KV Cache 换速度；
- 记录硬件、模型、量化、batch、上下文和推理服务版本。

## 9. 故障语义

- local 失败：任务明确失败在 local，不调用 cloud；
- cloud 失败：任务明确失败在 cloud，不调用 local；
- 某 chunk 失败：保存 checkpoint 和失败明细，可按同一 scope 恢复；
- 部分工单失败：总任务不能伪装全部完成；
- 验证未通过：前端显示真实原因，不能伪造绿色状态。

## 10. 退出条件

- 前端选中的 profile 与真实调用日志一致；
- 本地最小完整链路真实通过且无云端调用；
- 云端千问完成 100 条真实回放；
- local/cloud 并发配置完全分离；
- 云端达到性能目标或留下可复现的未通过基准，不能提前宣称完成；
- 性能提升没有改变 100/103、分类、主案例和负例结果。
