# 2026-03-24 Next Prompt

你现在接手的是一个已经完成云端 rerank 接入、query hard-case 收口和专项收益验证的 RAG 项目。不要再默认继续打磨同一批 rerank hard case，这一轮已经可以视为收口。

当前系统已经具备：
- 文档上传、异步入库、混合检索
- 文档级路由 / 分层检索
- query planner、focus extraction、多 query 融合
- metadata-aware local rerank
- DashScope `qwen3-rerank` 云端 rerank，带自动 fallback
- `queryDebug.rerank`、`routeRuns`、`retrievalRuns`、`attributionHints`、decision summary、eval compare、baseline 观测
- `small=10/10`、`query=8/8`、`medium=17/17`
- 专项 `rerank` 套件已经从 `5/8 -> 7/8 -> 8/8`

## 当前判断

这轮最重要的判断不是“还可以再挤一点 rerank 分数”，而是：

- 当前这条 query -> retrieval -> rerank 主链路已经足够完整
- 这轮 hard-case 收口已经完成
- 如果项目此刻暂停，是合理的
- 如果项目继续推进，下一步应该换一个范围，而不是继续在同一批 hard case 上反复抛光

## 如果后面还要继续，优先级建议

### 1. 维护型工作

优先考虑：

- 继续补少量高价值 eval case，但不要重启大规模 rerank 调参
- 偶尔回归 `small / query / medium / rerank`，确保没有回退
- 保持 README / notes / guidance 与当前实现一致

### 2. 新范围工作

如果要继续做功能，优先考虑新的范围，例如：

- 更系统的 long-doc / multi-hop eval
- 更完整的拒答与 citation 回归
- 更克制的单 Agent 试验
- 面向演示或面试表达的 docs / benchmark 整理

### 3. 暂时不建议做的事

- 不建议继续围绕当前这批 rerank hard case 做细碎调参
- 不建议再花很多精力接更多 rerank vendor
- 不建议在没有新评测目标的情况下继续堆 query 规则
- 不建议直接跳到复杂多 Agent 编排

## 总原则

- 当前 RAG 主链路已经超过 Demo 阶段，并完成了这一轮收口
- 之后若继续推进，应当明确换一个新的目标范围
- 若没有新的目标范围，最好的选择就是停在现在这个稳定版本
