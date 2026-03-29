# 2026-03-29 Personal Assistant Task Breakdown

这份文档把 `2026-03-29-personal-assistant-direction.md` 进一步拆成可执行任务清单。

目标不是抽象讨论，而是给后续实现提供：

- 明确的模块边界
- 推荐改造顺序
- 每一阶段的完成标准
- 尽量细颗粒度的待办项

---

## 总体目标

把当前项目从：

- `web-game + 多 session / 多 timeline 的互动叙事框架`

收紧到：

- `assistant-centric 的个人 AI 助手`

保留：

- `worldbook` 作为背景设定
- `character card` 作为助手人格
- `speech + narration` 的表达层
- RAG 检索能力
- 长期记忆持久化能力

重构：

- 顶层产品模型
- 前端信息架构
- 长期记忆归属
- retrieval 组织方式

---

## 执行原则

### 原则 1：先收口产品模型，再重构实现

不要一开始就同时：

- 改所有表
- 改所有命名
- 改所有前端页面
- 改所有 prompt

先把顶层心智收紧成 `assistant`，再做具体实现迁移。

### 原则 2：保留兼容层，逐步降级 session

短期内：

- 不必立刻删除所有 `session` 代码
- 但要把它从“产品主实体”降级成“内部存储边界”

### 原则 3：前端需要大改，不要误判成局部 UI 微调

这轮前端不是：

- 改几个文案
- 把按钮挪一挪

而是要整体从：

- `session workspace`

改成：

- `assistant workspace`

---

## Phase 0：定义新顶层模型

### 目标

明确之后所有层都围绕的核心对象：

- `assistant`

### 任务清单

1. 定义 `assistant` 的概念文档
   - 字段建议：
     - `id`
     - `name`
     - `worldbook_id`
     - `character_id`
     - `user_scope`
     - `status`
     - `created_at`
     - `updated_at`

2. 定义 `assistant` 与旧对象的关系
   - 一个 `assistant` 绑定一个 `worldbook`
   - 一个 `assistant` 绑定一个 `character card`
   - 一个 `assistant` 对应一个长期记忆空间
   - `session` 不再直接暴露为顶层产品实体

3. 明确旧对象的新定位
   - `worldbook`
     - 背景设定
   - `character`
     - 助手人格
   - `session`
     - 内部 conversation segment / snapshot

4. 明确用户心智变化
   - 从“新开一局”
   - 改成“进入某个助手”

### 完成标准

- 有清晰 assistant 数据模型草案
- 有一页文档写清旧模型如何映射到新模型

---

## Phase 1：前端信息架构重构

### 目标

把前端顶层交互从：

- session-oriented

改成：

- assistant-oriented

### 任务清单

#### 1. 顶层路由和页面心智重构

1. 梳理当前主界面的产品层级
   - 哪些组件仍默认围绕 `session`
   - 哪些组件已经接近“长期对话”

2. 重新定义顶层页面结构
   - 建议结构：
     - 左侧：assistant rail
     - 中间：persistent conversation stage
     - 右侧：assistant drawer

3. 移除或弱化这些默认文案/心智
   - 开局
   - 开幕舞台
   - 新的一局
   - 继续某条分支
   - 关系面板

#### 2. 左侧 Rail 重构为 Assistant Rail

1. 把当前 `SessionRail` 的职责拆解
   - session list
   - archived list
   - rename / archive / restore
   - recent restore

2. 设计新的 `AssistantRail`
   - assistant list
   - 当前助手入口
   - assistant avatar / name / summary
   - memory health / recent interaction indicator
   - snapshots/history 作为次级入口

3. 迁移 UI 状态
   - 当前选中对象从 `sessionId` 转为 `assistantId`
   - session 入口收进二级菜单

4. 保留旧 rail 的兼容期策略
   - 可以暂时保留 session rail 数据结构
   - 但 UI 主呈现必须先切 assistant 视角

#### 3. 中间主舞台重构为持续聊天界面

1. 重构主舞台命名和文案
   - 从 `DialogueStage / TurnSpotlight / 开幕舞台`
   - 转向 `AssistantConversation / ChatStage / ConversationPanel`

2. 弱化强叙事 framing
   - 去掉“开场 / spotlight / scene intro”的主入口感
   - 把 location/scene 降为轻信息

3. 保留 narration，但改定位
   - 低频旁白块
   - 默认是表达补充层
   - 不是剧情推进层

4. 调整输入区文案
   - 从“发送回合”
   - 改成更像持续聊天的输入心智

#### 4. 右侧抽屉重构

1. 把当前 `SceneInspector` 的信息重新分类
   - `Assistant Profile`
   - `Memory`
   - `Background`

2. 移除或重命名旧叙事化区块
   - 关系卡
   - 长期记忆时间线
   - 关系网格

3. 新建议结构
   - 助手印象
   - 长期主题
   - 最近重要记忆
   - 背景设定摘要

4. 让 history / snapshot 成为次级入口
   - 不再作为右侧抽屉主角

### 完成标准

- 主界面一眼看上去是“一个长期助手”，而不是“一个剧情工作台”
- 左侧主入口不再是 session list
- 中间主舞台不再强调“新开一局”

---

## Phase 2：后端数据模型收口

### 目标

把后端记忆归属从：

- `worldbook + character + session`

收口到：

- `assistant + user_scope`

### 任务清单

#### 1. 引入 assistant 存储模型

1. 设计 `assistants` 表 / 文件模型
   - `id`
   - `name`
   - `worldbook_id`
   - `character_id`
   - `user_scope`
   - `created_at`
   - `updated_at`
   - 可选 `status`

2. 明确 assistant 与现有 worldbook / character 的引用关系

3. 设计 assistant 的 API
   - create assistant
   - list assistants
   - get assistant
   - update assistant
   - delete assistant

#### 2. session 降级为内部 segment

1. 重新定义 `session` 语义
   - 从产品主实体改为内部 conversation segment

2. 给 session 增加 `assistant_id`

3. 把前端主 API 从 `currentSession` 迁向 `currentAssistant`

4. 保留旧接口一段时间作为兼容层

#### 3. 重构长期记忆归属

1. `game_memories` 增加或迁移为：
   - `assistant_id`
   - `user_scope`

2. `game_memory_profiles` 增加或迁移为：
   - `assistant_id`
   - `user_scope`

3. 保留 `worldbook_id` / `character_id` 作为辅助查询字段，但不再作为主归属

4. 规划迁移脚本
   - 从现有 `worldbook + character + player_scope` 推导 `assistant_id`

### 完成标准

- 可以明确回答“这条长期记忆属于哪个助手”
- 可以明确回答“当前显示的 profile 属于哪个助手”

---

## Phase 3：记忆系统分层重构

### 目标

把当前记忆系统从“working + episodic + profile”的雏形，推进成更适合 personal assistant 的分层结构。

### 任务清单

#### 1. 明确六层记忆模型

1. `conversation log`
2. `working memory`
3. `memory index`
4. `episodic memory`
5. `profile / semantic memory`
6. `knowledge graph`

#### 2. 给每一层定义职责

1. `conversation log`
   - 原始聊天记录

2. `working memory`
   - 当前几轮状态
   - 当前开放话题
   - 当前情感压力

3. `memory index`
   - 主题级索引
   - 轻量 summary
   - topic freshness

4. `episodic memory`
   - 具体发生过的互动

5. `profile / semantic memory`
   - 助手对用户的长期印象

6. `knowledge graph`
   - 稳定实体关系和事实

#### 3. 设计 memory index 第一版

1. 新增 `assistant_memory_index` 表草案
   - `assistant_id`
   - `user_scope`
   - `topic_key`
   - `topic_label`
   - `summary`
   - `memory_count`
   - `last_seen_at`
   - `representative_memory_ids`

2. 第一版 topic cluster 先规则化
   - 守约
   - 借伞
   - 道歉
   - 误会
   - 陪伴
   - 共同行动

3. retrieval 改造目标
   - 先查 profile
   - 再查 memory index
   - 再进入 episodic memory

#### 4. 重新设计 archive promotion

1. archive 不再只是把记忆写入 `game_memories`
2. archive 需要同时：
   - 写 episodic memory
   - 更新 memory index
   - 更新 assistant profile

### 完成标准

- 有清楚的 memory index 表设计
- archive 和 recall 的新链路有草图

---

## Phase 4：RAG 与未来 KG 的职责收口

### 目标

让长期记忆、RAG 和 KG 不再互相混淆。

### 任务清单

#### 1. 明确 RAG 职责

1. 外部文本证据
2. 用户导入资料
3. 世界书扩展文本
4. 可引用知识

#### 2. 明确 KG 职责

1. 实体
2. 稳定关系
3. 事实一致性
4. 长期偏好 / 长期约定

#### 3. 明确长期记忆职责

1. 你和助手发生过的事
2. 助手如何看待你
3. 哪些主题仍然开放

#### 4. 规划未来混合 retrieval

1. 先 profile / memory index
2. 再 episodic memory
3. 再 RAG
4. 再 KG constraints

### 完成标准

- 有一页文档能清楚区分 RAG / episodic / profile / KG 的边界

---

## Phase 5：Prompt 与生成链重构

### 目标

让 prompt 真正适配“personal assistant”，而不是继续沿用互动叙事框架的写法。

### 任务清单

#### 1. prompt 输入结构重构

1. 当前用户输入
2. 助手当前要回应的重点
3. 当前开放话题
4. profile summary
5. memory index 命中的 topic
6. 少量 episodic support
7. worldbook / character 作为背景层

#### 2. 降低叙事舞台感

1. 弱化 scene goal 外显感
2. 弱化“一局”的 framing
3. 弱化“推进剧情”的味道

#### 3. narration 收口

1. narration 默认可空
2. narration 低频
3. narration 来源更依赖当前互动
4. narration 少依赖 persona props

#### 4. 本地 post-check 继续弱化

1. 不再因为过短就强制替换
2. 不再用大面积 heuristic 覆盖模型原答
3. 只保留必要 hard constraints

### 完成标准

- 对话明显更像长期助手，而不是互动叙事角色

---

## Phase 6：迁移与兼容策略

### 目标

让旧数据、旧 UI、旧接口在一段时间内可兼容，而不是一次性硬切。

### 任务清单

1. 设计旧 session 到 assistant 的映射策略
2. 给旧长期记忆补 `assistant_id` 迁移脚本
3. 前端保留旧入口一段时间
4. 标记哪些接口是 legacy
5. 规划何时删除旧 `session-first` UI

### 完成标准

- 新旧数据都能过渡
- 没有“一次性切换导致全不可用”的风险

---

## Phase 7：验证与回归

### 目标

确保这轮是产品形态重构，不是单纯改概念。

### 任务清单

#### 1. 后端验证

1. assistant create/list/get/update/delete
2. session 与 assistant 的关联正确
3. archive 仍能沉淀长期记忆
4. recall 改成 assistant-centric 后仍能命中

#### 2. 前端验证

1. 首页默认是 assistant 入口，不是开新一局
2. 左侧 rail 主入口是 assistant
3. 右侧抽屉语义不再是关系面板
4. snapshots/history 是次级入口

#### 3. 对话验证

1. 助手能稳定引用背景设定
2. 助手能稳定引用长期记忆
3. narration 仍可用，但不过度喧宾夺主

#### 4. 产品判断验证

找人看页面时，能否直接理解成：

- “这是一个长期助手”

而不是：

- “这是一个互动剧情游戏”

### 完成标准

- 真实体验上，产品心智完成切换

---

## 建议的实际落地顺序

推荐按下面顺序做，而不要乱序并行：

1. 写清 `assistant` 数据模型
2. 画前端信息架构草图
3. 改左侧 rail / 主舞台 / 右侧抽屉
4. 给后端补 `assistant` 模型和 API
5. 把长期记忆改成 `assistant-centric`
6. 设计并接入 memory index
7. 再重写 prompt 输入结构
8. 最后规划 KG 融合

---

## 最小里程碑建议

如果只能先做一个最小但高价值的里程碑，建议定义成：

- 用户能创建并进入一个 `assistant`
- 前端主交互已经不再以 session/timeline 为核心
- 长期记忆已经明确归属于某个 assistant
- 助手能在持续对话中引用背景设定与长期记忆

这个里程碑一旦成立，项目就完成了从“叙事原型”到“personal assistant 框架”的真正转向。
