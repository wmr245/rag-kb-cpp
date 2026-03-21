# 基线别名

这个目录用于保存每个 suite 的“当前官方基线”。

默认约定：

- `small.json`
- `medium.json`
- `large.json`
- `longlite.json`
- `xlarge.json`

推荐工作流：

1. 先运行评测，确认当前结果稳定
2. 用 `python scripts/promote_eval_baseline.py --suite <suite>` 提升为官方基线
3. 后续运行时使用 `python scripts/run_eval.py --suite <suite> --compare-to-baseline`

建议：

- 日常默认维护 `small / medium / longlite`
- `xlarge` 只在阶段性验收时再提升基线
