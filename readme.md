# rag-kb-cpp

一个面向面试展示与逐步演进的项目，当前已经形成两条主线：

- `RAG` 主链路：`C++ Gateway + Python AI Service + PostgreSQL/pgvector + Redis`
- `web-game` 主链路：围绕开放世界恋爱叙事沙盒的会话工作台与长期记忆框架

这个项目刻意强调两件事：

1. AI 侧能力尽量手动实现，而不是一开始就依赖完整框架封装。
2. 按“先跑通，再优化，再扩展 Agent 能力”的方式渐进式演化，适合作为面试中的工程化作品集。

## 项目定位

这已经不只是一个知识库问答 Demo。当前仓库更准确的定位是：

- 一条已经相对收口的工程化 RAG 主链路
- 一条正在成型的长期聊天 / 叙事沙盒框架

它依然保持“手写核心链路优先”的风格，而不是一开始就依赖大框架封装。

目标是把下面这些能力逐步做实：

- 文档上传与异步入库
- 文档解析、切块、向量化
- 基于 pgvector 的向量检索
- 检索结果重排与引用生成
- 基于上下文的回答生成
- 查询缓存、任务状态、可观测性
- 后续扩展到 Agent 工作流

适合用于展示下面这些能力：

- 服务拆分与系统设计
- C++ 与 Python 混合架构协作
- RAG 核心流程的手动实现
- 数据库建模与向量检索落地
- 从基础问答系统逐步演进到 Agent 系统

## 当前架构

目录结构：

```text
.
├─ cpp-gateway/          # 对外 HTTP 网关，基于 Drogon
├─ python-ai/            # AI 核心服务，基于 FastAPI
├─ db/init/              # PostgreSQL 初始化脚本
├─ web-game/             # 游戏工作台前端
├─ game-data/            # 游戏 worldbook / character card / session 数据
├─ uploads/              # 上传文件共享目录
├─ scripts/              # 自测与辅助脚本
├─ eval/                 # 评测集、报告与基线
├─ notes/                # 迭代记录与问题复盘
├─ guidance/             # 阶段判断、下一步计划与架构指引
├─ docker-compose.yml    # 整体启动编排
└─ .env.example          # 示例环境变量
```

服务职责：

- `gateway`
  - 对外暴露接口
  - 接收用户上传的文件
  - 生成/透传 `x-trace-id`
  - 将查询、上传、任务查询转发给 AI 服务
- `ai-service`
  - 文档入库与任务状态管理
  - 文档解析、切块、Embedding 调用
  - 混合检索、规则重排、引用生成
  - Optional cloud rerank with automatic fallback
  - 基于证据评分决定回答或拒答
  - worldbook / character card / session / turn / memory 相关游戏服务
  - 使用 Redis 做查询缓存
- `postgres`
  - 存储文档、任务、切片、日志
  - 使用 `pgvector` 做向量相似度检索
- `redis`
  - 缓存查询结果
  - 存储知识库版本号等轻量状态
- `web-game`
  - 提供导入设定、会话管理、舞台窗口、剧情流和 memory timeline 等工作台界面

## 当前重点方向

RAG 主链路当前已经基本收口。新的主工作范围是：

- 把 `web-game` 从“能演一局”推进到“长期聊天框架”
- 长期目标不是继续堆 UI，而是做：
  - session 生命周期
  - archive 沉淀
  - 长期 episodic memory
  - profile / semantic memory
  - 后续 turn 的长期记忆召回

推荐先看：

- [guidance/2026-03-28-long-memory-architecture.md](guidance/2026-03-28-long-memory-architecture.md)
- [guidance/2026-03-28-next-prompt.md](guidance/2026-03-28-next-prompt.md)
- [notes/2026-03-28-session-workspace-lifecycle.md](notes/2026-03-28-session-workspace-lifecycle.md)

## 请求链路

### 1. 文档上传

```text
Client
  -> gateway /docs/upload
  -> 保存文件到 uploads/
  -> ai-service /internal/docs/upload
  -> 创建 docs/tasks 记录
  -> 后台执行 ingest
  -> 解析文档 / 切块 / 向量化 / 入库 chunks
```

### 2. 问答查询

```text
Client
  -> gateway /rag/query
  -> ai-service /internal/query
  -> Redis 查缓存
  -> Embedding 问题
  -> pgvector 向量召回 + 关键词召回
  -> optional cloud rerank
  -> 候选合并与规则重排
  -> 证据评估
  -> LLM 生成答案或拒答
  -> 返回 answer + items + citations
```

## 已实现能力

- `txt / md / pdf / docx` 文档读取
- 段落级切块与 overlap
- Markdown 标题感知切块
- Optional cloud rerank API integration with automatic fallback
- PDF 分页提取与按页保留 citation 信息
- PostgreSQL + pgvector + pg_trgm 的混合检索
- 基于向量分数、关键词召回、metadata、标题命中、结构顺序的重排
- 证据不足时的拒答策略
- 更贴近答案正文的 citation 对齐
- Redis 查询缓存
- 异步任务状态查询
- 网关层 trace id 与上游耗时透传

## 云端 Rerank 当前状态

- 已完成 DashScope `qwen3-rerank` 接入，当前接法是“本地规则重排后，对 top N candidate chunks 调云端 rerank，再融合分数”。
- 云端 rerank 失败时会自动回退到本地排序，不阻断主链路；状态会写入 `queryDebug.rerank`、`decisionSummary.retrieval` 和 eval compare。
- 在通用回归集上，`small=10/10`、`query=8/8`、`medium=17/17`，开启云端 rerank 后未出现 regression，但这些套件本身已经较强，因此没有体现通过率提升。
- 在专项 `rerank` 套件上，最初的结果为：`no-rerank 5/8`，`with-rerank 7/8`，证明云端 rerank 对“词面接近但语义目标不同”的 top1 排序有实际收益。
- 随后又补了一轮 query hard-case 收口和 retrieval observability，最终专项 `rerank` 套件达到 `8/8`，`header` 子集达到 `5/5`，当前这一轮已经可以视为收口状态。
- 这说明现在的收益不再只是“API 已接通”，而是已经形成“query planning + local retrieval + cloud rerank + hard-case eval”这一套完整闭环。

## 技术栈

### 网关层

- `C++17`
- `Drogon`
- `CMake`

### AI 服务层

- `Python 3.11`
- `FastAPI`
- `Uvicorn`
- `psycopg`
- `httpx`
- `redis`
- `pypdf`
- `python-docx`

### 基础设施

- `PostgreSQL`
- `pg_trgm`
- `pgvector`
- `Redis`
- `Docker Compose`

## 环境变量

项目实际运行时，`docker compose` 默认会读取仓库根目录下的 `.env`，`.env.example` 只是复制模板。

- `.env`：真正参与当前环境运行的配置文件
- `.env.example`：给新环境复制和参考的模板

当前默认 Embedding 已统一切到 `Qwen / DashScope text-embedding-v4`，并固定使用 `1536` 维，以便和现有向量列保持一致。

最少需要关注这些变量：

```bash
POSTGRES_DB=ragkb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_PORT=5433

REDIS_PORT=6379

AI_SERVICE_PORT=8000
GATEWAY_PORT=8080

EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_API_KEY=your_embedding_api_key
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIM=1536

LLM_PROVIDER=openai_compatible
LLM_API_KEY=your_llm_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus

RERANK_ENABLED=false
RERANK_PROVIDER=dashscope
RERANK_BASE_URL=https://dashscope.aliyuncs.com/compatible-api/v1/reranks
RERANK_API_KEY=your_rerank_api_key
RERANK_MODEL=qwen3-rerank
RERANK_TOP_N=20
RERANK_TIMEOUT_SEC=30
RERANK_SCORE_WEIGHT=0.65
LOCAL_RERANK_SCORE_WEIGHT=0.35
RERANK_INSTRUCT=Given a web search query, retrieve relevant passages that answer the query.
```

说明：

- `text-embedding-v4` 默认返回维度不是 `1536`，仓库代码里已经显式按 `EMBEDDING_DIM` 请求维度。
- 当前项目不建议直接切到 `text-embedding-v3`，因为它和现有 `1536` 维表结构不天然对齐。
- 如果你使用别的供应商，只要协议兼容 `/embeddings` 与 `/chat/completions`，通常不需要改核心链路。

## 快速开始

### 1. 准备环境变量

```bash
cp .env.example .env
```

然后编辑 `.env`。运行时真正生效的是 `.env`，不是 `.env.example`。

建议至少确认这些字段：

```bash
POSTGRES_DB=ragkb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_PORT=5433

REDIS_PORT=6379

AI_SERVICE_PORT=8000
GATEWAY_PORT=8080

EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_API_KEY=your_embedding_api_key
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIM=1536

LLM_PROVIDER=openai_compatible
LLM_API_KEY=your_llm_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus

RERANK_ENABLED=false
RERANK_PROVIDER=dashscope
RERANK_BASE_URL=https://dashscope.aliyuncs.com/compatible-api/v1/reranks
RERANK_API_KEY=your_rerank_api_key
RERANK_MODEL=qwen3-rerank
RERANK_TOP_N=20
RERANK_TIMEOUT_SEC=30
RERANK_SCORE_WEIGHT=0.65
LOCAL_RERANK_SCORE_WEIGHT=0.35
RERANK_INSTRUCT=Given a web search query, retrieve relevant passages that answer the query.
```

说明：

- `.env` 中的 `POSTGRES_PORT=5433` 是宿主机映射端口。
- `ai-service` 和 `gateway` 在 Docker 网络内部仍然访问 PostgreSQL `5432`。
- `gateway` 默认支持更大的上传体积，可通过 `GATEWAY_MAX_BODY_SIZE_MB` 调整。
- 如果只通过 `docker compose` 运行服务，通常不需要手动设置 `POSTGRES_HOST`、`REDIS_HOST`、`AI_SERVICE_HOST`。

### 2. Docker 一键启动

```bash
docker compose up --build -d
```

### 3. 查看服务状态

```bash
docker compose ps
```

### 4. 查看日志

```bash
docker compose logs -f
```

只看 AI 服务：

```bash
docker compose logs -f ai-service
```

只看网关：

```bash
docker compose logs -f gateway
```

### 5. 健康检查

AI 服务：

```bash
curl http://localhost:8000/health
```

网关：

```bash
curl http://localhost:8080/health
```

### 6. 停止服务

```bash
docker compose down
```

如果希望连数据卷一起删除：

```bash
docker compose down -v
```

注意：

- `docker compose down -v` 会删除数据库和 Redis 持久化数据。
- 面试演示时通常不要随手执行这个命令。

### 7. 跑一遍自测脚本

服务启动并通过健康检查后，可以直接运行：

```bash
python scripts/smoke_test.py
```

如果你要测试自己的文档：

```bash
python scripts/smoke_test.py   --file ./test.md   --question "这份文档主要讲了什么？"
```

### 8. 跑评测与回归

日常低成本回归建议按这个顺序：

```bash
python scripts/run_eval.py --suite small
python scripts/run_eval.py --suite query
python scripts/run_eval.py --suite medium
python scripts/run_eval.py --suite longlite
```

Cloud rerank rollout checklist:

```bash
python scripts/run_eval.py --suite small --compare-to-baseline
python scripts/run_eval.py --suite query --compare-to-baseline
python scripts/run_eval.py --suite medium --compare-to-baseline
```

针对云端 rerank 是否真的带来 top1 排序收益，建议再跑专项套件：

```bash
# baseline
python scripts/run_eval.py --suite rerank --report-out eval/reports/rerank-expanded-no-rerank.json --request-timeout 90

# with cloud rerank
python scripts/run_eval.py --suite rerank --report-out eval/reports/rerank-expanded-with-rerank.json --compare-to eval/reports/rerank-expanded-no-rerank.json --request-timeout 90
```

当前仓库里可以直接参考这三份专项结果：

- `rerank-expanded-no-rerank.json`: `5/8`
- `rerank-expanded-with-rerank.json`: `7/8`
- `rerank-hardcase-20260324-v3.json`: `8/8`
- `header` 子集最终达到：`5/5`

如果需要阶段性验证更大样本，再额外运行：

```bash
python scripts/run_eval.py --suite large
python scripts/run_eval.py --suite xlarge --request-timeout 120
```

说明：

- `longlite` 使用官方长文档摘录，适合在 embedding 免费额度有限时做长文档抽样回归。
- `xlarge` 会显著增加 embedding 开销，不建议作为默认日常测试。
- `small` 和 `longlite` 当前都已经在 `text-embedding-v4` 下回归通过。

## 接口说明

### 1. 上传文档

```bash
curl -X POST http://localhost:8080/docs/upload   -F "file=@./test.md"   -F "title=测试文档"   -F "owner=demo"
```

### 2. 查询任务状态

```bash
curl http://localhost:8080/tasks/<task_id>
```

### 3. 问答查询

```bash
curl -X POST http://localhost:8080/rag/query   -H "Content-Type: application/json"   -d '{
    "question": "这份文档主要讲了什么？",
    "topK": 3,
    "docScope": []
  }'
```

返回结果里会包含：

- `answer`：最终回答
- `refused`：是否因证据不足而拒答
- `refusalReason`：拒答原因
- `evidenceScore`：当前证据强度
- `queryDebug.rerank`：cloud rerank 的 provider / model / candidate count / applied count / fallback / latency，以及 local/final top items
- `items`：命中的 chunks，包含 `localScore` / `rerankScore` / `blendedScore`
- `citations`：引用信息
- `queryDebug`：query planner 的 focus / intent / decomposition / queries / timings
- `queryDebug.routeRuns`：每条 route query 的 top docs 调试快照
- `queryDebug.retrievalRuns`：每条 retrieval query 的 local/final top items 调试快照
- `queryDebug.attributionHints`：当前 case 的轻量归因提示
- `queryDebug.decisionSummary`：按 planner / routing / retrieval / answerability / citation 汇总的诊断视图
- `latencyMs`：总耗时

真实工作示例：

下面两段是 2026-03-21 在当前仓库环境里真实跑出来的精简响应，不是手写伪造样例。

正常回答示例：

```json
{
  "question": "RFC 9110 说 HTTP 是什么类型的协议？",
  "answer": "RFC 9110 将 HTTP 定义为一种**无状态的应用层协议**。",
  "refused": false,
  "refusalReason": null,
  "evidenceScore": 0.242426,
  "citations": [
    {
      "title": "RFC 9110 HTTP Semantics Excerpt",
      "page": 1,
      "snippet": "[Heading] Abstract The Hypertext Transfer Protocol (HTTP) is a stateless application-level protocol..."
    }
  ],
  "latencyMs": 1830
}
```

拒答示例：

```json
{
  "question": "这份文档里有 GPU 温度监控策略吗？",
  "answer": "根据当前检索到的内容，我还不能可靠回答这个问题。 当前命中的内容和问题关联度不够高，继续作答风险较大。",
  "refused": true,
  "refusalReason": "low_retrieval_confidence",
  "evidenceScore": 0.035006,
  "citations": [],
  "latencyMs": 389
}
```

从这两个例子可以看到：

- 有证据时，系统会正常作答，并把 citation 对齐到正文证据块。
- 证据不足时，系统会明确拒答，而不是勉强编造答案。

补充说明：

- 对外演示和联调优先使用网关公开接口：`/docs/upload`、`/tasks/{task_id}`、`/rag/query`
- AI 服务内部的 `/internal/*` 接口主要用于 gateway 转发，不建议作为默认外部入口

## 本地开发命令

### Python AI 服务

```bash
cd python-ai
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### C++ Gateway

```bash
cd cpp-gateway
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
./build/rag_gateway
```

## 数据库设计

主要表如下：

- `docs`
  - 文档元信息
  - 包含标题、来源路径、owner、状态
- `tasks`
  - 异步入库任务
  - 包含状态、进度、错误信息
- `chunks`
  - 文档切片
  - 包含文本、页码、向量与 metadata
- `rag_logs`
  - 查询日志
  - 用于后续做评估、性能分析、命中率统计

## 为什么这个项目适合作为面试项目

因为它不是“只会调接口”的 AI Demo，而是能展示比较完整的工程判断：

- 为什么把外部入口和 AI 核心逻辑拆成两个服务
- 为什么数据库选择 PostgreSQL + pgvector
- 为什么缓存放在 Redis
- 为什么切块、检索、重排、生成要拆成独立模块
- 为什么先手写核心链路，再考虑引入更复杂的 Agent 编排

## 分阶段路线图

### Phase 1：先把基础链路做稳

- 补齐 `.env.example` 与 README 中的配置说明，减少启动歧义
- 补充演示文档与最小测试数据，方便本地复现
- 统一日志字段、错误信息、trace id 透传规则
- 增加基础健康检查、任务失败排查信息、常见问题说明

### Phase 2：把 RAG 基础做扎实

- 增强 PDF 解析质量，处理表格、页眉页脚、重复页码等噪音
- 为 Markdown / Docx 保留更完整的章节层级信息
- 给 chunk 增加 metadata，如标题路径、章节层级、chunk 类型、页码
- 从固定长度切块升级为结构感知切块
- 针对标题、列表、表格、代码块采用不同切块策略

### Phase 3：优化召回与排序

- 从纯向量检索升级到混合检索：向量检索 + 关键词检索
- 设计多路召回、候选合并、去重策略
- 保留当前规则重排，并逐步引入轻量 reranker
- 针对标题问答、定义问答、步骤问答、结构定位问答加入 query 分类和检索偏置
- 优化 citation 截取逻辑，减少引用片段和答案不对齐的情况

### Phase 4：优化生成与缓存

- 按问题类型区分 Prompt 模板，例如总结型、定位型、对比型、定义型问题
- 增加证据不足时的拒答策略，降低幻觉
- 优化缓存 key 设计、知识库版本失效策略和近似问题缓存
- 补充结果可解释性字段，例如命中原因、重排得分、引用来源
- 根据真实查询数据优化 topK、候选数和响应耗时

### Phase 5：建立评测与回归体系

- 构建离线评测集，覆盖总结、定位、结构、定义、跨段问题
- 统计 Recall@K、MRR、命中率、答案准确率、引用准确率、延迟等指标
- 建立回归测试，防止优化召回后导致生成退化，或优化缓存后影响正确性
- 记录每次策略调整前后的指标变化，形成可复盘的优化过程

### Phase 6：在稳定 RAG 之上增加 Agent 能力

- 标准化工具接口和工具描述
- 为 Agent 提供检索前置、上下文准备和记忆管理能力
- 加入多步任务分解、工具选择、结果汇总的基础执行框架
- 优先实现可控、可解释、可调试的单 Agent 工作流
- 在基础稳定后，再考虑更复杂的多 Agent 协作
