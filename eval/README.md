# 评测集与回归脚本

这套评测集用于给当前 RAG 系统提供一个可持续扩展的回归基线，重点不是一次性追求“大而全”，而是先从稳定、可解释的小样本开始，再逐步扩大到更常见的知识库场景。

## 设计原则

- 先有 `small`，保证每次改检索策略都能在几十秒内回归。
- 再有 `medium`，覆盖产品说明、运行手册、API 参考、团队手册等常见内部知识库类型。
- 再用 `longlite` 保留长文档语义特征，但控制 embedding 开销。
- `xlarge` 只作为阶段性验收，不作为日常回归默认项。
- 每个 case 都同时看 `answer`、`items`、`citations`，避免只测生成不测检索。
- 对拒答问题也要看 `refused / refusalReason / citations`，避免系统“硬编答案”。

## 目录结构

```text
eval/
├─ corpus/             # 基础评测语料
├─ corpus_external/    # 外部长文档原始样本
├─ corpus_longlite/    # 长文档摘录版低成本语料
├─ suites/             # small / medium / large / longlite / xlarge
├─ reports/            # 运行报告输出目录（默认不提交）
├─ baselines/          # suite 基线别名
└─ README.md
```

## 套件说明

- `small`
  - 2 份文档，6 个 case
  - 覆盖 summary / definition / structure / procedure / troubleshooting
  - 适合每次调权重或改 rerank 后快速回归
- `medium`
  - 4 份文档，12 个 case
  - 增加 API 与团队规则场景
  - 适合评估“更像真实内部知识库”的效果
- `large`
  - 5 份文档，18 个 case
  - 增加 FAQ 和跨文档问题
  - 适合在做阶段性优化后观察整体稳定性
- `longlite`
  - 3 份官方长文档摘录，6 个 case
  - 保留 RFC 长文档里的关键定义与安全语义
  - 适合免费额度有限时做长文档抽样回归
- `xlarge`
  - 官方长文档抽样套件
  - 覆盖 RFC 长文档和 GovInfo PDF
  - 成本较高，建议在阶段性验收时再跑

## 当前默认建议

当前仓库默认运行配置已经统一到 `text-embedding-v4 + 1536 维`。

如果你在免费额度下做日常迭代，建议回归顺序固定为：

```bash
python scripts/run_eval.py --suite small
python scripts/run_eval.py --suite medium
python scripts/run_eval.py --suite longlite
```

如果需要阶段性验证更大样本，再额外运行：

```bash
python scripts/run_eval.py --suite large
python scripts/run_eval.py --suite xlarge --request-timeout 120
```

## 运行方式

先保证服务已启动：

```bash
python scripts/run_eval.py --suite small
```

也可以把报告写到指定路径：

```bash
python scripts/run_eval.py --suite medium --report-out eval/reports/medium-latest.json
```

## 如何扩展

新增评测时，优先按下面顺序扩展：

1. 先补新语料到 `eval/corpus/` 或 `eval/corpus_longlite/`
2. 再把新 case 加到合适的 suite
3. 为 case 打上清晰 `tags`，例如 `summary / api / procedure / policy / refusal / cross_doc`
4. 尽量让断言落在“稳定事实”上，比如关键短语、标题路径、citation 标题
5. 如果要评估新策略，优先先看 `small` 是否回归，再看 `medium / longlite / large`

## 对比模式

如果你已经有历史报告，可以直接比较两次评测结果：

```bash
python scripts/compare_eval_reports.py   --baseline eval/reports/small-older.json   --current eval/reports/small-newer.json
```

如果你想边跑边比，也可以在执行评测时直接带上基线：

```bash
python scripts/run_eval.py   --suite small   --compare-to eval/reports/small-older.json
```

如果希望在发现回退时返回非零退出码，可以加：

```bash
python scripts/run_eval.py   --suite medium   --compare-to eval/reports/medium-baseline.json   --fail-on-regression
```

## 基线别名工作流

设置官方基线：

```bash
python scripts/promote_eval_baseline.py --suite small
python scripts/promote_eval_baseline.py --suite medium
python scripts/promote_eval_baseline.py --suite longlite
```

之后直接按 suite 别名对比：

```bash
python scripts/run_eval.py --suite small --compare-to-baseline
python scripts/run_eval.py --suite medium --compare-to-baseline --fail-on-regression
python scripts/run_eval.py --suite longlite --compare-to-baseline
```

如果当前运行结果确认稳定，也可以边跑边提升基线：

```bash
python scripts/run_eval.py --suite small --promote-baseline
```

外部长文档来源说明见 `eval/corpus_external/README.md` 和 `eval/external_sources.md`。
