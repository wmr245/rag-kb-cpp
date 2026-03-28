# 评测集与回归说明

这套 `eval/` 目录的目标，不是做一个花哨的大 benchmark，而是给当前 RAG 系统提供一套“能日常回归、能看出哪里退化了、能支撑后续优化”的工程化评测体系。

如果你现在看 report 有点乱，可以先记住下面 4 句话：

- `suite` 是一套题。
- `report` 是某次跑题的结果。
- `baseline` 是被认定为“当前官方参考成绩”的那份 report。
- `compare-to-baseline` 是把本次结果和官方参考成绩做对比。

## 1. 目录结构

```text
eval/
├─ corpus/             # 基础评测语料
├─ corpus_external/    # 外部长文档原始样本
├─ corpus_longlite/    # 长文档摘录版低成本语料
├─ suites/             # small / query / medium / large / longlite / xlarge / rerank
├─ reports/            # 每次运行生成的报告
├─ baselines/          # 各 suite 的官方基线别名
└─ README.md
```

## 2. 先理解这几个概念

### `suite`

`suite` 就是一套固定题目，定义在 `eval/suites/*.json`。

它通常包含两部分：
- `documents`：这次跑评测前要上传的文档
- `cases`：要问哪些问题、预期答案里应包含什么、应命中什么 citation

### `report`

`report` 是某次执行 `python scripts/run_eval.py ...` 之后生成的结果文件，默认写到 `eval/reports/`。

它记录：
- 这次用了哪些文档
- 每个 case 的结果
- 总通过数
- debug 统计
- 如果带了 compare，还会记录 comparison

### `baseline`

`baseline` 不是模型，也不是数据库快照。

在这个项目里，`baseline` 的意思是：
某个 suite 当前被认可的“官方参考 report”。

比如：
- `eval/baselines/small.json`
- `eval/baselines/query.json`
- `eval/baselines/medium.json`

以后系统改动后再跑同一套 suite，就拿新 report 和它比，判断有没有回退。

### `compare-to-baseline`

这表示：
- 先跑当前系统
- 再读取对应 suite 的 baseline
- 最后输出本次结果相对 baseline 的差异

它不是重新跑两次系统，而是“当前 report vs 官方参考 report”的对比。

## 3. 当前各套件适合干什么

### `small`

- 2 份文档，10 个 case
- 最小日常回归套件
- 重点覆盖：summary / definition / structure / procedure / routing / paraphrase

适合：
- 改完 query planner、routing、retrieval 后第一时间跑

### `query`

- 4 份文档，8 个 case
- 专门测 query handling
- 重点覆盖：rewrite / mixed query / decomposition / refusal

适合：
- 调 query understanding
- 看 `queryDebug` 和 `decisionSummary`
- 看 compare 里的原因归因

### `medium`

- 4 份文档，17 个 case
- 更接近真实内部知识库
- 加入 API、团队规则、默认路由、拒答等场景

适合：
- 做比较大的策略改动后再跑
- 验证“不是只在小样本上过拟合”

### `large`

- 5 份文档，18 个 case
- 增加 FAQ 和跨文档问题

适合：
- 阶段性验收

### `longlite`

- 3 份长文档摘录，6 个 case
- 保留长文档语义特征，但控制 embedding 开销

适合：
- 免费额度有限时做长文档抽样验证

### `rerank`

- 2 份文档，8 个 case
- 专门测 top1 排序与语义接近干扰项

适合：
- 调云端 rerank
- 调 query planner / retrieval hard-case
- 验证“最终答案没退化，但 top item 是否真的更对了”

### `xlarge`

- 官方长文档抽样套件
- 成本高，不建议日常默认跑

适合：
- 阶段性验收

## 4. 日常怎么跑最合适

如果你只是日常改代码，不要每次都跑全家桶。

推荐顺序：

```bash
python scripts/run_eval.py --suite small --compare-to-baseline --request-timeout 90
python scripts/run_eval.py --suite query --compare-to-baseline --request-timeout 90
```

如果这次改动涉及更大范围的 routing / rerank / refusal，再加：

```bash
python scripts/run_eval.py --suite medium --compare-to-baseline --request-timeout 90
```

如果这次改动主要在 rerank、query hard-case 或 top1 排序，再额外跑：

```bash
python scripts/run_eval.py --suite rerank --compare-to-baseline --request-timeout 90
```

只有阶段性验收时，再考虑：

```bash
python scripts/run_eval.py --suite large
python scripts/run_eval.py --suite longlite
python scripts/run_eval.py --suite xlarge --request-timeout 120
```

## 5. report 里最重要的字段怎么读

一个 report 顶层大概长这样：

```json
{
  "suiteId": "query",
  "totals": {...},
  "tagStats": {...},
  "debugSummary": {...},
  "results": [...],
  "comparison": {...}
}
```

### `totals`

先看这里。

它告诉你：
- 一共多少 case
- 过了多少
- `answerAll / answerAny / retrieval / citation / refusal` 分别过了多少

这是最快判断“这次有没有整体退化”的入口。

### `tagStats`

这是按标签汇总的通过情况。

比如你只改了 query planner，就优先看：
- `query`
- `routing`
- `decomposition`
- `refusal`

## 6. `debugSummary` 是干什么的

`debugSummary` 是整份 report 的诊断概览，不看单 case 也能先知道这次系统整体做了什么。

现在它通常包含：
- `plannerVersions`
- `intentCounts`
- `routingModes`
- `refusalReasons`
- `casesWithDecomposition`
- `casesWithAutoRouting`
- `refusedCases`
- `casesWithDecisionSummary`
- `casesWithRerankEnabled`
- `casesWithRerankApplied`
- `casesWithRerankFallback`
- `rerankProviders`

你可以把它理解成“这一轮运行的全局画像”。

例子：
- `routingModes.auto = 5` 说明有 5 条 case 走了自动文档路由
- `intentCounts.api = 5` 说明这轮有 5 条 query 被 planner 判成 API 类
- `refusalReasons.low_retrieval_confidence = 1` 说明有 1 条 case 是因为证据不足而拒答

## 7. 单个 case 要怎么看

`results` 数组里每个元素就是一个 case 的结果。

建议按下面顺序看：

1. `passed`
2. `answer`
3. `topItems`
4. `citations`
5. `decisionSummary`
6. `queryDebug`

### `answer`

这是最终回答。

### `topItems`

这是评测脚本提炼后的 top retrieval 结果，重点看：
- 命中的标题对不对
- 命中的 heading / sectionPath 对不对
- 命中 sourceType 对不对

### `citations`

看引用有没有贴到正确文档，以及 snippet 是否和答案一致。

### `decisionSummary`

这是现在最推荐优先看的字段。

它比 `queryDebug` 更像“人能直接读懂的诊断结论”，通常长这样：

```json
{
  "headline": "Answered after auto-routed; planner intent=temporal, multiPart; evidence=0.420 (strong).",
  "planner": {...},
  "routing": {...},
  "retrieval": {...},
  "answerability": {...},
  "citation": {...}
}
```

它把一次问答压成 5 段：
- `planner`：问题被怎么理解
- `routing`：路由到了哪几篇文档
- `retrieval`：最终保留了哪些 chunk
- `answerability`：是否拒答、证据强弱如何
- `citation`：最后挂了哪些引用

如果你只是排查“这次为什么不对”，优先看它，而不是先扎进原始 `queryDebug`。

### `queryDebug`

这是更底层的调试信息，适合需要细看时再打开。

它包括：
- `normalizedQuestion`
- `focusQuestion`
- `decomposition`
- `intent`
- `routeQueries`
- `retrievalQueries`
- `timingsMs`

你可以把它理解成“decisionSummary 背后的原始材料”。

## 8. compare 输出怎么读

如果你用了：

```bash
python scripts/run_eval.py --suite query --compare-to-baseline --request-timeout 90
```

report 里会多一个 `comparison` 字段。

### 先看这几个字段

- `totalsDelta`
- `regressionCount`
- `improvementCount`
- `regressions`
- `improvements`
- `changedCases`

### `totalsDelta`

表示当前结果和 baseline 相比的总变化。

比如：
- `passed=+0`：总通过数没变
- `retrieval=-1`：retrieval 维度少过了 1 条
- `citation=+2`：citation 维度多过了 2 条

### `regressions` / `improvements`

这里是最关键的差异列表。

现在每个变化 case 都会带：
- `reasonAreas`
- `reasonSummary`
- `reasonDetails`

这意味着 compare 不只是告诉你“退化了”，还会直接提示更像是哪一层出了问题：
- `planner`
- `routing`
- `retrieval`
- `answerability`
- `citation`

### `regressionReasonBuckets` / `improvementReasonBuckets` / `changedReasonBuckets`

这是按原因领域做的聚合统计。

比如：
- `{"routing": 3, "retrieval": 2}`

意思更接近：
这次变化主要集中在 routing 和 retrieval，而不是 citation 或 refusal。

注意：
- `changedReasonBuckets` 包含的是“发生变化的 case”，不一定都是回退
- 它更像变化热区，不等于故障清单

## 9. 常见误解

### 为什么 `changed=8`，但 `regressions=0`？

因为这里的 `changed` 往往只是：
- 延迟变了
- route/retrieval 细节变了
- 但最终通过结果没退化

这不一定是坏事。

### 为什么有时 `latencyMs=1`？

通常是缓存命中，不是异常。

### 为什么 compare 里有些变化看起来很多？

因为 compare 现在已经会看：
- planner
- routing
- retrieval
- answerability
- citation

所以即使最终 `passed` 没变，它也可能告诉你“内部路径变了”。

### 为什么 baseline 不会自动更新？

因为 baseline 的作用就是固定参考标准。

如果每次都自动更新，那你就失去了“跟旧标准比较”的意义。

## 10. baseline 工作流

### 设置官方 baseline

```bash
python scripts/promote_eval_baseline.py --suite small
python scripts/promote_eval_baseline.py --suite query
python scripts/promote_eval_baseline.py --suite medium
python scripts/promote_eval_baseline.py --suite rerank
```

### 日常回归

```bash
python scripts/run_eval.py --suite small --compare-to-baseline --request-timeout 90
python scripts/run_eval.py --suite query --compare-to-baseline --request-timeout 90
python scripts/run_eval.py --suite medium --compare-to-baseline --request-timeout 90
python scripts/run_eval.py --suite rerank --compare-to-baseline --request-timeout 90
```

### 只有确认结果稳定后，再提升 baseline

```bash
python scripts/run_eval.py --suite query --compare-to-baseline --promote-baseline --request-timeout 90
```

## 11. 怎么扩展新的评测 case

建议顺序：

1. 先补语料到 `eval/corpus/` 或 `eval/corpus_longlite/`
2. 再把 case 加到合适的 suite
3. 用清晰的 `tags`
4. 断言尽量写“稳定事实”，不要写太脆弱的自然语言表述
5. 改完先跑 `small / query`，再决定要不要跑 `medium / rerank`

断言优先级建议：
- 先断言核心事实短语
- 再断言 retrieval 命中文档/heading
- 再断言 citation 标题
- 最后才考虑更细的答案措辞

## 12. 当前最推荐的使用方式

如果你以后只想记一套最省心的流程，就记这个：

1. 改代码
2. 跑 `small --compare-to-baseline`
3. 跑 `query --compare-to-baseline`
4. 如果改动比较大，再跑 `medium --compare-to-baseline`
5. 如果改的是 top1 排序或 rerank，再跑 `rerank --compare-to-baseline`
6. 先看 `totalsDelta`
7. 再看 `regressions`
8. 最后用 `decisionSummary` 和 `reasonSummary` 定位问题

这样你就不会再被 report 里的字段淹没，而是能按固定顺序排查。

## 13. 补充

- 外部长文档来源说明见 `eval/corpus_external/README.md` 和 `eval/external_sources.md`
- 当前默认 embedding 运行配置是 `text-embedding-v4 + 1536`
- 如果免费额度紧张，优先跑 `small / query / medium`，按需补 `rerank`，不要默认跑 `xlarge`

## Rerank Debug

When cloud rerank is enabled, check `queryDebug.rerank` in each case result. It tells you whether rerank was enabled, how many candidates were sent, whether fallback happened, and how much latency rerank added.
