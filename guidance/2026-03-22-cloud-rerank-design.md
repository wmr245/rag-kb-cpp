# 2026-03-22 Cloud Rerank Design

这份文档用于说明：在当前仓库结构下，如何以最低风险接入一个云端 rerank API，把现有的“规则 + metadata-aware rerank”升级成“召回后由 learned reranker 做最终排序”的形态。

## 目标

目标不是推翻当前 RAG 主链路，而是在现有能力基础上加一层更强的相关性排序：

1. 保留当前 query planner、文档级路由、混合检索、contextual chunk。
2. 先召回一批候选 chunk。
3. 把这些候选交给云端 rerank API 打分。
4. 用 rerank score 重新排序，再进入 answer / refusal / citation。
5. 如果 rerank API 失败，自动回退到当前本地规则排序。

## 为什么值得做

当前仓库已经有很多正确且必要的规则：
- query intent / focus / decomposition
- routing threshold / domain alignment / dedupe
- metadata-aware rerank
- refusal threshold
- citation alignment

这些规则在工程上是合理的，但现在已经接近“规则法收益递减”的阶段。

最值得替换成 learned component 的位置，不是 query planner，也不是 routing，而是“候选 chunk 的最终排序”。

原因：
- 这一步最直接影响最终命中的 top items。
- 这一步对 citation 对齐和 answer quality 的影响最大。
- 这一步最容易用现有 eval / baseline / compare 去量化收益。

## 当前链路与建议插入点

当前主链路近似为：

`question -> query planner -> route docs -> hybrid retrieve chunks -> local rerank -> answerability -> generate -> citations`

建议接入后变为：

`question -> query planner -> route docs -> hybrid retrieve chunks -> local rerank(top N candidates) -> cloud rerank -> answerability -> generate -> citations`

这里的关键点是：
- 云端 rerank 不替代召回，只替代最终排序的主导权。
- 本地 rerank 仍然保留，作为候选压缩和失败回退层。
- 只对 top N 候选调用云端 API，避免成本和延迟失控。

## 推荐的工程设计

### 1. 新增环境变量

建议新增：

```env
RERANK_ENABLED=false
RERANK_PROVIDER=
RERANK_BASE_URL=
RERANK_API_KEY=
RERANK_MODEL=
RERANK_TOP_N=20
RERANK_TIMEOUT_SEC=30
RERANK_SCORE_WEIGHT=0.65
LOCAL_RERANK_SCORE_WEIGHT=0.35
```

默认建议：
- `RERANK_ENABLED=false`
  先确保开关存在，再按需打开。
- `RERANK_TOP_N=20`
  大多数 case 足够。
- `RERANK_SCORE_WEIGHT=0.65`
  让云端 rerank 成为主要排序信号，但不完全抛弃本地分数。

### 2. 新增服务文件

建议新增：
- `python-ai/app/services/rerank_service.py`

职责：
- 统一封装云端 rerank API 调用
- 输入：`query + candidate documents`
- 输出：`[{index, score}]`
- 失败时抛出可控异常或返回空结果

建议的接口形态：

```python
def rerank_candidates(query: str, documents: list[str], top_n: int) -> list[dict]:
    ...
```

文档文本建议直接用：
- `context_text`

不要只用原始 `text`，因为我们前一轮已经专门把 chunk 上下文化了。

### 3. 在 retrieval_service.py 中的接入位置

建议接在 `search_chunks()` 内部：

1. 先保留当前：
   - vector recall
   - keyword recall
   - merge candidates
   - local rerank
2. 对 local rerank 后的前 `RERANK_TOP_N` 个候选构造 rerank documents
3. 调 `rerank_service.rerank_candidates(...)`
4. 用 rerank score 和当前 `final_score` 做融合
5. 再取 top_k 返回

建议融合公式：

```text
blended_score =
  rerank_score * RERANK_SCORE_WEIGHT
  + local_final_score * LOCAL_RERANK_SCORE_WEIGHT
```

这样做的原因：
- rerank 分数是 learned 相关性信号
- local 分数仍然保留 metadata / structure / lexical 的工程约束
- 失败时也容易平滑回退

## 候选文档如何构造

候选传给 rerank API 的 `document` 建议直接使用：
- `context_text`

同时在返回和 debug 里保留：
- `text`
- `heading`
- `section_path`
- `chunk_type`
- `source_type`
- `local_final_score`
- `rerank_score`
- `blended_score`

原因：
- rerank 吃 `context_text` 才能理解 chunk 属于哪篇文档、哪个 section
- 生成和 citation 仍要依赖原始 `text`

## 失败回退设计

这是工程里非常重要的一层，必须明确：

### 回退原则

如果出现下面任一情况：
- API 超时
- 返回格式异常
- 限流 / 5xx
- score 数量不匹配

就直接回退到当前本地排序结果，不影响主链路可用性。

### 建议实现

- `rerank_service.py` 负责把失败记录成日志
- `retrieval_service.py` 捕获异常后：
  - 保留 local rerank 结果
  - 在 `queryDebug` / `decisionSummary` 里写明 `rerankFallback=true`

## observability 怎么接

接入 rerank 后，建议把这些字段补进 `queryDebug`：
- `rerankEnabled`
- `rerankProvider`
- `rerankModel`
- `rerankCandidateCount`
- `rerankAppliedCount`
- `rerankFallback`
- `rerankLatencyMs`

同时把 `decisionSummary.retrieval` 扩展成可读描述，例如：
- `Local retrieval produced 20 candidates; cloud rerank re-ordered the top 20 and final top chunk is ...`

compare-to-baseline 也应加入新的原因域：
- `rerank`

这样以后如果 regression 发生，就能区分：
- 是 planner 变了
- 是 routing 变了
- 是 retrieval 变了
- 还是 rerank 本身引起的

## eval 怎么接

接入 rerank 后，不建议马上扩大数据集，而是优先复用现有：
- `small`
- `query`
- `medium`

建议顺序：

1. 先开 `RERANK_ENABLED=false` 跑一次，确认没有链路变化。
2. 再开 `RERANK_ENABLED=true`，跑：
   - `small --compare-to-baseline`
   - `query --compare-to-baseline`
   - `medium --compare-to-baseline`
3. 重点看：
   - `retrieval`
   - `citation`
   - `reasonBuckets`
   - `decisionSummary`

### 最值得新增的专项 case

如果要补专门的 rerank case，优先补：
- 定义类问题，容易命中“标题像对、正文不够对”的 chunk
- 结构定位类问题，容易混到邻近 section
- 多意图 query，容易召回很多似是而非的候选
- citation 对齐 case，观察 lead citation 是否更贴正文

## 当前仓库里建议修改的文件

### 必改

- `python-ai/app/core/config.py`
  - 新增 rerank 配置项
- `python-ai/app/services/rerank_service.py`
  - 新增云端 rerank API 封装
- `python-ai/app/services/retrieval_service.py`
  - 在 `search_chunks()` 中接入 rerank
- `python-ai/app/models/schemas.py`
  - 让 debug / decision summary 可承载 rerank 字段
- `python-ai/app/routers/internal.py`
  - 把 rerank 观测写进响应
- `scripts/run_eval.py`
  - 让 report / compare 能看到 rerank 调试信息
- `readme.md`
  - 更新环境变量和功能说明
- `eval/README.md`
  - 更新如何看 rerank 相关输出

### 可能要改

- `.env.example`
  - 增加 rerank 配置示例
- `guidance/README.md`
  - 如果下一轮要正式推进 rerank，可以补一个入口说明

## 分阶段落地建议

### Phase A：接通但默认关闭

先完成：
- 配置项
- 服务封装
- debug 字段
- fallback 机制

目标：
- 不开启时，系统行为和今天一致
- 便于安全上线和对比

### Phase B：只对 top 20 候选启用

目标：
- 观察真实收益
- 控制延迟和成本

### Phase C：再决定是否让 rerank 成为默认主排序

只有在 `small / query / medium` 都稳定，并且 compare 里能看出收益时，再考虑把 rerank 作为默认主导排序。

## 风险与注意事项

### 1. 延迟上升

rerank 会增加一次远程调用。

解决方式：
- 限制 top N
- 控制 timeout
- 失败快速回退

### 2. 成本上升

这是接云端 API 的天然代价。

解决方式：
- 不对所有候选都 rerank
- 只对最有价值的 top 20 候选 rerank
- 先在 `small / query / medium` 验证收益

### 3. 如果把 rerank 接得过深，排错会变难

解决方式：
- 不要让 rerank 替代 routing
- 不要让 rerank 替代 refusal
- 只让 rerank 负责最终相关性排序

## 最终建议

当前仓库最适合的接入方式是：
- 保留现有 query planner、routing、hybrid recall、contextual chunk
- 在 `search_chunks()` 里对 top 20 候选接云端 rerank
- 保留本地分数作为融合项和失败回退项
- 把 rerank 调试信息接进现有 `decisionSummary / eval / compare / baseline`

这样做的好处是：
- 改动范围可控
- 质量收益最可能直接体现到 top items / citations / answer quality
- 和当前工程化体系最兼容
- 做完后再进入单 Agent，会比现在更稳
