# 2026-03-28 Long Memory Architecture

这份文档定义“长期聊天框架”在当前仓库里的可落地实现方案。目标不是抽象讨论“记忆应该很智能”，而是明确：

- 哪些记忆继续留在 session 内
- 哪些记忆要进入长期存储
- 为什么不能直接把游戏记忆塞进现有文档 RAG 表
- 写入、召回、归档、压缩应该接在现有代码的哪些位置

---

## 1. 当前基础与判断

仓库当前已经有两块可复用基础：

- 游戏侧已有 session 内记忆雏形
  - `python-ai/app/models/game_schemas.py`
  - `python-ai/app/services/state_update_service.py`
  - `python-ai/app/services/memory_retrieval_service.py`
- RAG 侧已有 PostgreSQL + pgvector + pg_trgm 的成熟底座
  - `db/init/001_init.sql`
  - `python-ai/app/services/retrieval_service.py`

但这两块目前还没有打通成“长期聊天框架”。

当前 `memoryEntries` 的特点是：

- 挂在 `GameSession` 内
- 生命周期跟单个 session 绑定
- 召回只在当前 session 内做规则排序
- 没有跨 session、跨归档、跨角色画像的持久层

这意味着：

- 它足够支撑“短时演出”
- 还不足以支撑“长期陪伴”

---

## 2. 不建议直接复用现有 `docs/chunks`

现有文档 RAG 表服务的是“静态知识库”，而长期角色记忆服务的是“动态关系状态”。这两类数据虽然都能用 embedding 检索，但不应该混进同一组表。

原因：

- 文档 chunk 的写入频率低、更新稀疏，游戏记忆写入频率高、会持续增长
- 文档检索关注证据准确率，角色记忆检索关注相关性、时间衰减、情绪显著度、关系上下文
- 文档 chunk 通常不需要归档压缩，长期记忆必须考虑 promotion / merge / summarization
- 文档表当前服务 `/internal/query`，游戏记忆应该服务 `/game/*` 路径，避免产品语义混淆

结论：

- 复用 pgvector、pg_trgm、混合检索思路
- 不复用现有 `docs/chunks` 作为游戏记忆表

---

## 3. 目标形态：三层记忆

长期聊天框架建议拆成三层：

### A. Working Memory

作用：

- 保存当前 session 的最近对话、当前 scene、当前 active events、当前关系态

当前承载位置：

- `GameSession.recentTurns`
- `GameSession.runtimeState`
- `GameSession.memoryEntries`
- `GameSession.memoryProfiles`

保留原因：

- 它是当前一局的热上下文
- 延迟最低
- 不需要每轮都走向量检索

### B. Episodic Memory

作用：

- 存储具体事件记忆
- 后续 turn 可按语义、角色、地点、事件线索召回

示例：

- “雨天借伞”
- “图书馆陪伴到闭馆”
- “在天台第一次正面冲突”
- “因为承诺而提升 trust”

特点：

- 适合 embedding
- 可跨 session 召回
- 可做 salience 排序和时间衰减

### C. Semantic / Profile Memory

作用：

- 存储总结性记忆，而不是具体片段

示例：

- 当前关系阶段
- 对玩家的总体印象
- 角色的主要敏感点 / 偏好
- 重要事件索引
- 最近 unresolved thread

特点：

- 更短、更稳
- 适合直接注入 prompt
- 适合作为 archive 后沉淀结果

---

## 4. 最小可落地数据模型

MVP 不建议一开始建太多表。优先两张主表，必要时再补 link 表。

### 4.1 `game_memories`

建议用途：

- 承接长期 episodic memory

建议字段：

- `id`
- `worldbook_id`
- `session_id`
- `responder_id`
- `character_ids`
- `location_id`
- `scene_id`
- `day_index`
- `memory_type`
  - `event`
  - `promise`
  - `conflict`
  - `secret`
  - `bonding`
  - `milestone`
- `summary`
  - 给 prompt 注入的短摘要
- `retrieval_text`
  - 用于 embedding / lexical retrieval 的展开文本
- `trigger_hints`
  - 关键词、事件种子、角色名
- `emotion_payload`
  - 可记录 valence / arousal 或 trust/affection/tension 变化
- `relation_payload`
  - 可记录 `trust_delta / affection_delta / tension_delta / familiarity_delta`
- `salience`
  - 0~1 或 0~100
- `importance`
  - 业务层长期重要度
- `visibility`
  - player / director / character 可见性
- `archived_from_session`
  - 是否从 session promotion 而来
- `last_used_at`
- `created_at`
- `updated_at`
- `embedding VECTOR(1536)`

索引建议：

- `(worldbook_id, created_at desc)`
- `(session_id, created_at desc)`
- `(responder_id, created_at desc)`
- trigram on `summary / retrieval_text`
- ivfflat on `embedding`

### 4.2 `game_memory_profiles`

建议用途：

- 承接 semantic/profile memory

建议字段：

- `id`
- `worldbook_id`
- `character_id`
- `player_scope`
  - MVP 可以固定为单玩家
- `latest_session_id`
- `relationship_stage`
- `trust`
- `affection`
- `tension`
- `familiarity`
- `player_image_summary`
- `relationship_summary`
- `long_term_summary`
- `open_threads`
- `important_memory_ids`
- `last_interaction_at`
- `created_at`
- `updated_at`

索引建议：

- unique `(worldbook_id, character_id, player_scope)`
- `(worldbook_id, updated_at desc)`

### 4.3 Phase 2 可选：`game_memory_links`

仅在后续需要更强图谱化关联时再加：

- memory -> memory 的因果/引用关系
- memory -> profile 的索引关系
- session -> promoted memory 的追踪关系

MVP 不强制。

---

## 5. 写入策略：不要“随机记忆”，而要“显著度驱动”

长期记忆不建议随机写入。建议使用：

- 规则信号
- 情绪/关系阈值
- LLM summarizer 判定

三者混合。

### 5.1 必记规则

出现这些情况时，直接生成 memory candidate：

- 承诺 / 陪伴 / 道歉
- 冲突 / 失约 / 拒绝
- 秘密解锁
- 关系阶段跃迁
- 活动事件第一次触发
- 明显的地点或关系转折

### 5.2 情绪阈值 / 关系阈值

建议加入一层显著度评分：

- `abs(trust_delta) >= 3`
- `abs(affection_delta) >= 3`
- `abs(tension_delta) >= 3`
- stage changed
- secret unlocked
- event seed 首次进入 active

当任一条件成立时，提高 `salience`。

### 5.3 LLM 判定输出

在 `apply_turn_result()` 之后或 turn plan 末尾新增一层轻量 summarizer：

- `should_memorize`
- `memory_type`
- `summary`
- `retrieval_text`
- `salience`
- `emotion_payload`

要求：

- 只产结构化 JSON
- 不直接改 session
- 由服务层决定是否入库

这样可以避免“全靠 prompt 决策”导致记忆写入不可控。

---

## 6. 召回策略：先短时，再长期

每轮 turn 不应该把所有记忆塞进 prompt。建议按优先级召回：

### 层 1. Working Memory

直接注入：

- 最近 4~6 轮对话
- 当前 scene / 当前 cast
- 当前 active events
- 当前 relationship state

### 层 2. Semantic Profile

每个 responder 注入：

- `relationship_summary`
- `player_image_summary`
- `open_threads`

### 层 3. Episodic Memory Retrieval

输入：

- 当前玩家输入
- 当前 responder
- 当前地点
- 当前 active events

召回：

- `game_memories` top-k

排序建议：

- semantic similarity
- responder 命中
- location 命中
- trigger hint 命中
- salience
- recency decay
- 最近是否已注入过

MVP 可先用：

- vector + trigger + location + recency 的加权分

不要一开始就做太复杂的 agent policy。

---

## 7. 归档策略：session 结束后做一次沉淀

长期聊天框架的关键不只是“边聊边记”，还包括“归档沉淀”。

建议在 session 从 `active -> archived` 时执行：

### Archive Pipeline

1. 收集当前 session 的高 salience memory candidates  
2. 去重 / 合并相似事件  
3. 写入 `game_memories`  
4. 生成或更新 `game_memory_profiles`  
5. 为每个角色更新：
- `relationship_summary`
- `player_image_summary`
- `open_threads`
- `important_memory_ids`

这样 archived session 就不只是“冻结”，而是变成后续新局可继承的记忆源。

---

## 8. 对现有代码的接入点

### 8.1 第一阶段新增模块

建议新增：

- `python-ai/app/services/long_memory_service.py`
  - 负责持久化长期记忆
- `python-ai/app/services/long_memory_retrieval_service.py`
  - 负责跨 session 检索
- `python-ai/app/services/session_archive_service.py`
  - 负责 archive promotion / profile merge

### 8.2 优先修改的现有文件

- `db/init/001_init.sql`
  - 新增长期记忆表
- `python-ai/app/models/game_schemas.py`
  - 增加长期记忆相关 schema
- `python-ai/app/services/state_update_service.py`
  - 输出 memory candidate
- `python-ai/app/services/memory_retrieval_service.py`
  - 从“只查 session”扩展到“session + long-term”
- `python-ai/app/services/game_session_service.py`
  - 在 archive / play_turn 时挂入长期记忆逻辑
- `python-ai/app/routers/game.py`
  - 提供 profile / memory timeline / archive summary 接口

---

## 9. MVP 实施顺序

建议按下面顺序，而不是一步做满：

### Phase 1. Long Memory Storage

- 新增 `game_memories`
- 新增 `game_memory_profiles`
- 保持现有 session memory 不动
- 先打通 archive 时 promotion

### Phase 2. Retrieval Integration

- turn 阶段召回长期 memory
- 将 profile summary 注入 director / responder prompt

### Phase 3. Salience Writing

- 增加 per-turn memory candidate
- 对高显著事件实时写长期 memory

### Phase 4. Compression / Merge

- 对重复事件归并
- 对过长记忆做总结压缩
- 做 archive summary 和长期 profile merge

---

## 10. 验收标准

做到下面这些，才算“长期聊天框架”开始成立：

- 一个 session 归档后，关键信息不会只留在单个 session JSON 里
- 新 session 开场时，角色能继承之前的关系摘要与关键事件记忆
- archived session 不会继续写入 turn
- 长期 memory 检索不会污染文档 RAG 主链路
- 前端工作台能看到 memory timeline、active/archived 生命周期和恢复逻辑

---

## 11. 当前推荐判断

如果项目目标是“构建一个较为长期的聊天框架”，那么下一步最值得做的，不是继续打磨前端壳子，而是：

- 先完成长期记忆后端持久层
- 再把 retrieval 注回 game turn
- 最后再扩充前端观测与管理界面

顺序不要反过来。
