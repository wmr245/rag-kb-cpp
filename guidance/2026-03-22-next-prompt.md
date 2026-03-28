# 2026-03-22 Next Prompt

你现在接手的是一个已经完成文档级路由和第一轮 query handling 收口的 RAG 项目，不要重复回到“先做路由”或者“先证明系统能跑”的阶段。请基于现状继续推进。

当前系统已经具备：
- 文档上传、异步入库、混合检索
- chunk metadata（heading / sectionPath / chunkType / sourceType）
- metadata-aware rerank
- 文档级路由 / 分层检索
- 路由候选去重、最小分数阈值、领域约束
- query planner、focus extraction、多 query 融合
- 拒答策略与 citation 对齐
- smoke test、分层评测集、报告对比、baseline 机制
- `small` 套件已达到 `10/10`
- 默认 embedding 运行配置已统一为 `text-embedding-v4 + 1536`

当前主要目标不是继续大范围堆规则，而是把 query 侧做得更系统，并为 Agent 做好最后一层底座准备。

## 1. 继续完善 Query Handling

目标：
- 系统化扩展 query rewrite、focus extraction、decomposition
- 覆盖更多口语化、模糊表达、多意图和多跳问题
- 避免 definition / summary / procedural 之间的误判再次拖偏检索

要求：
- 不要只靠词表堆叠
- 优先采用结构化 query understanding：intent、focus、slot、subquery
- 原问题、focus query、rewrite query 可以并行召回后融合
- 每次改动必须用 eval 验证，而不是凭感觉判断

## 2. 扩充 Query 评测覆盖

需要新增评测 case，至少覆盖：
- 中文口语 paraphrase
- 英文或中英混合问法
- 多意图问题
- query decomposition 场景
- 明确应该拒答的问题

目标不是只看 answer 是否包含关键词，还要确认：
- 命中的 heading 是否对
- citation 是否仍然贴正文
- rewrite 没有把问题改坏
- 拒答没有明显退化

## 3. 增加可观测性

目标：
- 让 query planner 产出的 intent、focus、queries 更容易追踪
- 让 routing、retrieval、answerability 的关键决策可回看
- 为以后单 Agent 排错做准备

建议：
- 继续保留轻量日志
- 适当把关键 planner 字段纳入 eval 报告或调试输出
- 暂时不必引入很重的 tracing 平台，但要把链路观测留好

## 4. 批判性评估当前短板

请默认延续下面这个判断，不要回到“系统已经没什么可做了”的结论：

- 当前 RAG 已经超过 Demo 阶段
- 文档级路由和第一轮 query planner 已经补齐了大坑
- 但 query coverage 还不够广，observability 也还不够强
- 在进入 Agent 之前，最值得继续补的是 query understanding 和链路观测
- 如果这一步没做稳，Agent 只会把排错难度放大

## 5. Agent 的启动边界

只有当下面条件基本满足时，再开始做第一版 Agent：
- query handling 的评测覆盖明显扩充
- 默认无 `docScope` 的问答体验稳定
- query planner / routing / retrieval 的关键决策可观测
- 拒答和 citation 没有明显回退

开始 Agent 时：
- 先做单 Agent
- 只负责查询范围判定、必要时问题拆解、调用现有检索与回答链路
- 不要一上来做多 Agent 编排
- Agent 的效果必须继续纳入现有 eval / compare / baseline 体系

总原则：
- 继续沿用现有工程化方法
- 优先做“可验证提升”的改动
- 不要为了看起来更智能而牺牲可控性、引用对齐和拒答稳定性
