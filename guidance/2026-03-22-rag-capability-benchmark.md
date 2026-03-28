# 2026-03-22 RAG Capability Benchmark

这份文档用于把当前仓库的 RAG 能力，和近一年更常见的前沿 RAG 系统能力做一个工程化对照，帮助判断下一步应该继续补 RAG，还是可以进入 Agent。

## 对照范围

这里不把“前沿”理解成某一个框架名字，而是理解成当前主流先进系统普遍具备的能力组合。主要参考：

- Anthropic 提出的 Contextual Retrieval：强调 contextual embeddings、contextual BM25 和 reranking 叠加带来的检索收益。
- Cohere 官方 Rerank 文档：强调把 rerank 作为独立运行时组件，而不是只靠初筛召回。
- OpenAI 2025 的 Agents / File Search 方向：强调 file search、metadata filtering、custom reranking、observability、evaluations 等能力已经成为产品级默认组件。

参考资料：
- Anthropic, Introducing Contextual Retrieval: https://www.anthropic.com/engineering/contextual-retrieval
- Cohere, An Overview of Cohere's Rerank Model: https://docs.cohere.com/v2/docs/rerank-overview
- OpenAI, New tools for building agents: https://openai.com/index/new-tools-for-building-agents/

## 阶段更新

当前仓库相比上一轮已经新增：
- 文档级路由 / 分层检索
- 路由候选去重、分数阈值和领域约束
- query planner、focus extraction、多 query 融合
- `small` 套件从 `8/10` 修复到 `10/10`

这意味着项目已经进入“RAG 底座基本成型，开始做 query understanding 和 Agent 前准备”的阶段。

## 功能对照表

| 能力方向 | 前沿系统常见做法 | 当前仓库现状 | 判断 | 下一步建议 |
|---|---|---|---|---|
| 基础文档入库 | 异步导入、切块、可复现索引 | 已具备 | 达标 | 保持稳定 |
| 结构化 metadata | 标题、层级、来源、过滤字段全链路保留 | 已具备 `heading/sectionPath/chunkType/sourceType` | 达标 | 继续利用到路由和评测 |
| 混合检索 | semantic + lexical 一起召回，再融合 | 已具备 `pgvector + pg_trgm` | 达标 | 后续可继续优化融合策略 |
| 文档级路由 | 先路由到文档或知识库，再做 chunk 检索 | 已具备 | 达标 | 继续扩评测覆盖 |
| Query Understanding | normalize、intent、rewrite、focus、decomposition | 已有第一轮 query planner 和多 query 融合 | 半成型 | 当前最高优先级 |
| Contextual Retrieval | 给 chunk 补文档级上下文，再建 embedding / BM25 | 还没有系统化做 contextualized chunk | 有缺口 | 值得排进后续 RAG 优化队列 |
| 专门 reranker | 使用独立 rerank 模型做二次排序 | 目前以规则和 metadata-aware rerank 为主 | 有缺口 | query 稳定后再考虑 |
| 元数据过滤 | 按来源、角色、文档范围、时间过滤 | 具备基础 `docScope` 能力和自动路由 | 半成型 | 继续往更面向用户的默认体验推进 |
| citation 对齐 | 尽量贴正文证据块，减少“只贴标题” | 已做改进 | 有进步 | 后续可继续往句子级对齐走 |
| 拒答 | 证据不足时明确拒答 | 已具备 `refused/refusalReason/evidenceScore` | 达标 | 增加拒答专项评测 |
| 评测闭环 | 固定数据集、报告对比、基线机制 | 已具备 | 亮点 | 继续补 query 场景覆盖 |
| Tracing / Observability | 能追踪检索、rerank、工具执行链路 | 目前主要依赖日志和评测脚本 | 有缺口 | Agent 前最好补一些可观测性 |
| Agent-ready Tooling | 检索能力被稳定封装成可调用工具 | 已有雏形，但未正式做 agent orchestration | 可启动前准备中 | query 和观测收口后进入 |

## 关键判断

### 1. 现在的系统已经不只是 Demo

当前仓库已经具备：
- 混合检索
- metadata-aware rerank
- 文档级路由
- query planner
- citation 对齐
- 拒答策略
- smoke test
- eval / compare / baseline
- 真实运行配置统一

这说明系统已经进入“可持续迭代”的工程阶段，而不是只会跑一个 happy path 的样例项目。

### 2. RAG 本体还有提升空间，但重心已经变化

当前最主要的缺口，不再是“有没有文档级路由”，而是：
- query understanding 覆盖是否够广
- observability 是否足够支持后续 Agent 排错
- contextual retrieval / 专门 reranker 是否值得接入

也就是说，RAG 还没结束，但最该补的点已经从 routing 切到了 query 和观测。

### 3. 为什么现在还不该直接全力转复杂 Agent

更成熟的系统并不是“Agent 取代 RAG”，而是“Agent 建在更稳的 retrieval、query understanding、guardrails、eval 和 observability 之上”。

如果现在直接上复杂 Agent，最大风险是：
- Agent 会调度一个 query coverage 还不够广的检索底座
- 改写错误和查询范围误判会被放大
- 排错会变难，收益却不稳定

### 4. 什么情况下可以开始 Agent

当下面三个条件满足时，就可以开始做第一版 Agent：
- query handling 的评测覆盖已经扩开
- planner / routing / retrieval 的关键决策已经较容易观察
- 默认无 `docScope` 的用户体验已经稳定

## 建议路线

### 现在最值得做

1. 继续扩 query rewrite / decomposition。
2. 把 query 类 case 纳入更广的 eval 覆盖。
3. 增强 planner、routing、retrieval 的可观测性。

### 做完后再做

1. 评估是否接入更强的专门 reranker。
2. 评估 contextual retrieval 是否值得补。
3. 再做单 Agent，而不是直接做多 Agent。

## 最终结论

当前最稳妥的判断不是“RAG 已经结束”，也不是“现在马上应该堆 Agent”，而是：

先把 query understanding 和链路观测再收紧一轮，把 RAG 底座再抬高半步；然后再进入单 Agent，会比现在直接跳过去更像一个成熟系统的演进路线。
