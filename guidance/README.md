# Guidance Directory

这个目录统一存放项目级协作指引、阶段判断、下一步提示词，以及适合后续接手工作的边界说明。

## 文件说明

- `AGENT_GUIDE.md`
  项目级协作与演进原则，说明默认优化顺序、环境约束和沟通方式。
- `2026-03-21-next-prompt.md`
  第一轮阶段提示词，记录从文档级路由开始收口 RAG 底座的目标。
- `2026-03-22-next-prompt.md`
  上一轮 query handling 冲刺提示词，聚焦 query rewrite、decomposition 和进入 Agent 前的最后一轮 RAG 收口。
- `2026-03-22-rag-capability-benchmark.md`
  当前 RAG 能力对照与阶段判断，用来说明还缺哪些能力，以及什么时候适合进入 Agent 阶段。
- `2026-03-22-cloud-rerank-design.md`
  云端 rerank API 接入设计，说明为什么接、接在哪里、如何回退，以及怎么纳入 eval。
- `2026-03-24-next-prompt.md`
  当前稳定版之后的收口判断，说明这轮 RAG 主链路已经可以停在稳定版本；如继续推进，应切换到新范围。
- `2026-03-27-reusable-interfaces.md`
  当前仓库里已经可以收口成复用接口的边界说明。用于后续拆服务、分语言职责、或者在新产品方向上复用既有 RAG 能力时，明确哪些层应该被包装成稳定接口，哪些实现细节暂时不要定死。
- `2026-03-28-long-memory-architecture.md`
  长期聊天框架的可落地方案，说明三层记忆、长期存储建模、archive 沉淀、retrieval 接入顺序，以及为什么不要直接复用现有文档 `chunks` 表。
- `2026-03-28-next-prompt.md`
  当前最值得推进的新范围提示词，明确下一步应该把项目从“会话工作台”推进到“长期记忆后端 + 归档沉淀 + turn 检索”。

## 当前使用方式

- 需要了解仓库协作规则时，先看 `AGENT_GUIDE.md`
- 需要判断当前项目是否还该继续深挖同一批 hard case 时，优先看 `2026-03-24-next-prompt.md`
- 需要把现有能力包装成更稳定的服务边界、供后续 Java 产品层或新 Agent 编排复用时，优先看 `2026-03-27-reusable-interfaces.md`
- 需要开始做长期聊天框架的后端设计时，优先看 `2026-03-28-long-memory-architecture.md`
- 需要判断当前项目接下来该怎么推进、按什么顺序推进时，优先看 `2026-03-28-next-prompt.md`
- 需要回看上一轮 query handling 冲刺目标时，再参考 `2026-03-22-next-prompt.md`
- 需要做阶段判断或能力对照时，参考 `2026-03-22-rag-capability-benchmark.md`
- 需要回看云端 rerank 的设计背景时，参考 `2026-03-22-cloud-rerank-design.md`

## 当前判断

当前项目已经超过 Demo 阶段，并且已经完成：

- 文档级路由 / 分层检索
- 路由候选去重和噪声压制
- query planner、focus extraction、多 query 融合检索
- DashScope 云端 rerank 接入、fallback、专项收益验证
- query hard-case 收口与 retrieval observability 补齐
- `small=10/10`、`query=8/8`、`medium=17/17`
- 专项 `rerank` 套件 `5/8 -> 7/8 -> 8/8`

当前最稳妥的结论是：

- 这一轮 RAG 主链路已经可以收口
- 如果没有新的目标范围，可以停在这个稳定版本
- 如果后面还要继续推进，应切到新的工作范围，而不是继续在同一批 rerank hard case 上反复打磨

当前已经明确的新范围是：

- `web-game` 的 session workspace 已经具备第一层生命周期能力
- 项目下一步最值得做的是长期记忆后端，而不是继续主要投入视觉层或 rerank 微调
