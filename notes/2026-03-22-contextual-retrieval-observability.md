# 2026-03-22 Contextual Retrieval And Observability Update

## Goal

这一轮工作的目标有两块：

1. 把已有的 `queryDebug` 和 compare 输出，升级成更像“诊断视图”的可观测能力。
2. 在不推翻现有混合检索链路的前提下，把 chunk 检索升级成带上下文的 contextual retrieval，并进一步强化本地 rerank。

## Why This Work Was Needed

### 1. 之前的调试信息太像原始材料，不像诊断结论

已有能力：
- `queryDebug`
- compare-to-baseline
- baseline 机制

问题：
- 信息是有的，但更像“原始字段堆在一起”
- 真要排查时，仍然要人工拼出：
  - planner 做了什么
  - route 到了哪几篇文档
  - retrieval 最终命中了什么
  - 为什么拒答 / 不拒答
  - citation 是怎么来的

目的：
- 把排错成本降下来
- 为后续接 reranker 和单 Agent 做准备

### 2. 当前 rerank 仍以规则法为主，质量上限开始逼近

已有能力：
- metadata-aware rerank
- routing thresholds
- domain alignment
- refusal threshold
- citation heuristic

这些做法是工程上合理的，但已经进入“继续堆规则，收益会越来越低”的阶段。

目的：
- 先把 chunk 本身做成更强的上下文化检索对象
- 再为后续接 learned reranker 做铺垫

## What Was Changed

### 1. 把 queryDebug 升级成 decisionSummary

文件：
- `python-ai/app/models/schemas.py`
- `python-ai/app/routers/internal.py`
- `scripts/run_eval.py`

方法：
- 新增 `DecisionSummary` / `DecisionSummarySection`
- 每次查询把结果压成 5 段：
  - `planner`
  - `routing`
  - `retrieval`
  - `answerability`
  - `citation`
- 报告里保留原始 `queryDebug`，同时额外写入：
  - `decisionSummary`
  - `decisionSummaryText`

为什么这么做：
- 先给人一眼能读懂的诊断结果
- 再保留原始字段做深挖
- 这样比只加日志更适合后续 compare 和回归

### 2. compare-to-baseline 增加原因归因

文件：
- `scripts/run_eval.py`

方法：
- 给每个变化 case 新增：
  - `reasonAreas`
  - `reasonSummary`
  - `reasonDetails`
- 在 comparison 顶层新增：
  - `regressionReasonBuckets`
  - `improvementReasonBuckets`
  - `changedReasonBuckets`

原因分类：
- `planner`
- `routing`
- `retrieval`
- `answerability`
- `citation`

为什么这么做：
- 以前 compare 只能告诉我们“变了没有”
- 现在开始告诉我们“更像是哪一层引起的变化”

### 3. 评测说明重写，降低 report 使用门槛

文件：
- `eval/README.md`
- `readme.md`

方法：
- 重新解释 `suite / report / baseline / compare-to-baseline`
- 明确 report 顶层字段怎么读
- 明确单个 case 该先看什么
- 明确 `decisionSummary` 和 `comparison` 的用途

为什么这么做：
- 之前 report 结构已经有了，但对人不够友好
- 如果未来要继续积累评测体系，就必须让它更好读

### 4. 引入 contextual chunk

文件：
- `db/init/001_init.sql`
- `python-ai/app/db/postgres.py`
- `python-ai/app/services/document_service.py`
- `python-ai/app/services/ingest_service.py`
- `python-ai/app/core/lifespan.py`
- `python-ai/app/services/retrieval_service.py`
- `python-ai/app/services/cache_service.py`

方法：
- 给 `chunks` 新增 `context_text`
- 为每个 chunk 构造上下文化文本，包含：
  - document title
  - source type
  - section path
  - heading
  - chunk type
  - content body
- 新文档入库时，embedding 改为对 `context_text` 生成
- 历史数据启动时自动回填缺失的 `context_text`
- 关键词检索和本地 rerank 也开始优先使用 `context_text`

为什么这么做：
- 原始 chunk 文本有时缺乏“它属于哪篇文档、哪个 section”的信息
- contextual chunk 更接近 Anthropic 所说的 contextual retrieval 思路
- 这是一个比直接硬接 learned reranker 更低风险的中间升级

### 5. 强化本地 rerank

文件：
- `python-ai/app/services/retrieval_service.py`

方法：
- 保留现有 hybrid recall
- 在本地 rerank 中，把 `context_text` 加入：
  - keyword overlap
  - phrase hit
  - keyword recall material
- 不动最终 answer / refusal / citation 接口

为什么这么做：
- 先用 contextual chunk 把候选质量抬起来
- 再决定是否接云端专门 reranker

## Engineering Problems Encountered

### 1. compare 输出会被临时 docId 噪声污染

问题：
- compare 中用 `resolvedDocScope` 做差异比较时，每次重新上传都会得到新的临时 `docId`
- 这会把测试环境本身的变化误判成 routing 变化

解决：
- 取消把 `resolvedDocScope` 作为主要原因归因材料
- 改成更关注真正稳定的 routedDocs / topItems / citations

收益：
- compare 原因归因更接近真实行为变化

### 2. 评测断言会被空格和标点差异误伤

问题：
- 像 `周五 17:00` 和 `周五17:00` 这种语义等价写法会被误判成 regression

解决：
- 给 eval 的答案匹配补了轻量规范化
- 比较前先去掉空格和常见标点噪声

收益：
- report 更可信，不再把措辞细节当成系统退化

### 3. contextual retrieval 改动触发了 SQL 参数错配

问题：
- 给 chunk 关键词检索增加 `context_text` 后，`similarity_expr` 的 `%s` 数量变了
- 初次接入时，`keyword_filter_params` 和 `exec_params` 没有完全同步更新
- 运行时 `/rag/query` 报了 `placeholders vs parameters mismatch`

解决：
- 逐段检查 `_fetch_keyword_rows()` 和 `_fetch_doc_keyword_rows()`
- 对齐占位符数和问题参数数目
- 重建 `ai-service` 后重新跑回归

收益：
- contextual retrieval 最终稳定落地
- 也说明这轮改动是实打实通过运行验证的，不是只改了代码没跑通

## Validation Results

### Observability

最新阶段结果：
- `decisionSummary` 已进入 query 响应和 eval report
- compare 输出已支持原因归因
- report 里新增了更直观的：
  - `debugSummary`
  - `reasonAreas`
  - `reasonSummary`
  - `reasonBuckets`

### Contextual Retrieval

最新回归结果：
- `small`: `10/10`
  - report: `eval/reports/small-20260322-181920.json`
- `query`: `8/8`
  - report: `eval/reports/query-20260322-181951.json`
- `medium`: `17/17`
  - report: `eval/reports/medium-20260322-181959.json`

结果：
- contextual chunk 没有打坏现有 query / routing / refusal / citation 体系
- stronger local rerank 已经和现有 baseline 体系兼容

## Improvement Impact

### 1. 可观测性提升

现在不再只有“原始调试字段”，而是开始有：
- 面向人的 `decisionSummary`
- 面向 compare 的原因归因
- 面向 suite 的 `debugSummary`

效果：
- 排错更快
- 更容易判断问题到底更像在 planner、routing、retrieval 还是 citation

### 2. 检索对象质量提升

通过 `context_text`，chunk 不再只是孤立文本，而是带上了：
- 文档标题
- section path
- heading
- source type
- chunk type

效果：
- embedding 更能理解 chunk 所处语境
- lexical recall 更能命中带结构语义的问题
- local rerank 可以更自然地利用结构信息

### 3. 为专门 reranker 做好铺垫

这一轮不是直接上云端 rerank，而是先把下面这几层打稳：
- contextual chunk
- stronger local rerank
- better observability
- compare reason analysis

效果：
- 下一步接云端 rerank 的收益会更清楚
- 出问题时也更容易判断是不是 rerank 本身导致的

## Current Judgment

这轮之后，项目已经具备：
- query planner
- document routing
- hybrid retrieval
- contextual chunk
- local rerank
- refusal
- citation
- eval / baseline / compare
- compare reason analysis

所以现在继续往前走，最自然的一步不是再堆更多规则，而是：
- 接云端专门 reranker
- 让 learned model 接管最终排序主导权

## Recommended Next Step

下一步推荐：
1. 接云端 rerank API
2. 只对 top N chunk 候选做 rerank
3. 保留本地分数作为 fallback 和融合项
4. 把 rerank 信号接进 `decisionSummary / eval / compare`

结论：
- 这轮工作把“规则驱动的稳定底座”又往上抬了一步
- 接云端 rerank 已经从“可以考虑”变成了“下一步最自然的演进”
