# 第一阶段任务清单

## 1. 阶段目标

第一阶段不是把整个游戏做完，而是把“可持续迭代的底座”搭起来。

这一阶段完成后，应该至少具备：

- 可导入一个 `worldbook`
- 可导入多张 `character card`
- 可创建一个 `game session`
- 可保存和恢复运行状态
- 可在单场景下进行连续对话
- 可在对话中稳定保留世界设定、角色设定和关系变化
- 可为后续导演 Agent 和网页界面提供清晰接口

一句话目标：

“先做出一个结构稳定、记忆连续、接口清晰的单人叙事内核。”

## 2. 范围约束

第一阶段只做最小可用闭环，不做这些：

- 多人房间
- 可视地图编辑器
- 多 Agent 自治
- 复杂战斗系统
- 复杂养成系统
- 大量前端演出效果

第一阶段只聚焦四件事：

1. 内容输入
2. 状态与记忆
3. 运行时编排
4. 最小交互入口

## 3. 模块划分

第一阶段建议拆成以下模块。

### 3.1 Canon 模块

负责静态设定真相：

- `worldbook_service`
- `character_card_service`
- `canon_validation_service`

### 3.2 Session 模块

负责一局游戏的运行状态：

- `game_session_service`
- `runtime_state_service`
- `state_persistence_service`

### 3.3 Memory 模块

负责动态记忆：

- `recent_turns_service`
- `memory_entry_service`
- `memory_profile_service`
- `memory_retrieval_service`

### 3.4 Narrative 模块

负责运行时叙事编排：

- `scene_resolver_service`
- `director_agent_service`
- `character_response_service`
- `state_update_service`

### 3.5 Interface 模块

负责给外部产品层调用：

- `worldbook_import_api`
- `character_card_import_api`
- `game_session_api`
- `game_turn_api`

## 4. 第一阶段任务清单

### A. 内容输入层

1. 定义 `worldbook schema`
2. 定义 `character card schema`
3. 做 schema 校验与错误提示
4. 设计 canon 存储模型
5. 实现导入与查询接口

交付标准：

- 可以导入一个合法 `worldbook`
- 可以导入多张合法角色卡
- 非法字段、缺失字段、引用错误能被准确报出

### B. 状态与记忆层

1. 定义 `game session` 数据结构
2. 定义 `runtime state` 数据结构
3. 定义 `memory_entry` 和 `memory_profile`
4. 定义状态读写边界
5. 实现最近对话窗口保存
6. 实现关键事件写入动态记忆
7. 实现 session 存档恢复

交付标准：

- 连续 20 轮对话后，角色不明显失忆
- 关系值、已触发事件、已解锁秘密能恢复
- 世界观与角色设定不会被运行时回复污染

### C. 运行时编排层

1. 定义 `game_turn` 输入输出协议
2. 实现场景解析器 `scene_resolver`
3. 实现第一版导演 Agent
4. 实现角色响应层
5. 实现状态更新器
6. 接入现有 RAG 查询接口用于设定和记忆召回

交付标准：

- 每轮输入都能得到稳定的：场景、回应、状态变化
- 角色回复引用正确世界设定和角色设定
- 关键事件会驱动状态变化和记忆写回

### D. 最小产品入口

1. 做一个最小会话 API
2. 做一个最小调试 API
3. 做一个简单网页或页面壳
4. 展示当前场景、对话、角色状态、最近事件

交付标准：

- 单人可试玩
- 可以开始一局、继续一局、恢复一局
- 能看到最基本的状态变化与调试信息

## 5. 推荐实现顺序

推荐严格按下面顺序做，不要倒着来。

1. `worldbook schema`
2. `character card schema`
3. `game session / runtime state / memory` 数据结构
4. `canon import + validation`
5. `session create / load / save`
6. `scene resolver`
7. `director agent`
8. `character response`
9. `state updater`
10. `minimal game turn api`
11. `minimal web ui`

原因：

- schema 不稳定，后面所有东西都会反复返工
- 状态结构没定，记忆就不可能稳定
- 运行时编排要建立在稳定数据层上
- UI 最后做，避免前期被演示层拖慢

## 6. 第一阶段对外接口建议

建议第一阶段只冻结这几类接口：

### 6.1 Canon 接口

- `create_worldbook`
- `get_worldbook`
- `list_worldbooks`
- `create_character_card`
- `get_character_card`
- `list_character_cards`

### 6.2 Session 接口

- `create_game_session`
- `get_game_session`
- `save_game_session`
- `resume_game_session`

### 6.3 Turn 接口

- `play_turn`
- `get_turn_debug`

### 6.4 Memory 接口

- `append_memory_entry`
- `query_memory_entries`
- `refresh_memory_profile`

## 7. 模块化编程要求

第一阶段必须遵守这些约束：

### 7.1 Canon 只读优先

- `worldbook` 和 `character card` 是 canon
- 普通游戏过程不能直接改写 canon
- 运行时变化只能写到 `runtime state`

### 7.2 状态更新集中化

- 不允许导演 Agent、角色响应层、前端各自偷偷改状态
- 只能由 `state_update_service` 统一修改 `runtime state`

### 7.3 记忆读写分离

- 读取记忆由 `memory_retrieval_service` 负责
- 写入记忆由 `memory_entry_service` 负责
- 角色生成时不能顺手篡改记忆

### 7.4 场景解析与角色生成分离

- `scene_resolver` 负责决定当前场景和出场角色
- `character_response_service` 负责生成台词
- 不要把“谁该出现”和“说什么”混成一个黑盒 prompt

### 7.5 调试信息从第一天就保留

建议每轮保留：

- 召回了哪些 canon
- 召回了哪些记忆
- 当前场景是如何决定的
- 哪些状态字段被修改了
- 为什么触发了某个事件

## 8. 第一阶段验收标准

阶段完成时，至少满足：

- 一个 `worldbook` + 三张角色卡可以完整导入
- 能创建并恢复 session
- 能连续对话 20 轮以上
- 角色关系和关键事件能持续保存
- 关键秘密不会无故泄露
- 世界观和角色设定不会明显漂移
- 新模块边界清晰，后续可继续接 Agent 或网页产品层

## 9. 最值得警惕的风险

### 9.1 先做 UI，后补状态

这是最容易返工的路径，不建议。

### 9.2 把 canon 和 runtime 混在一起

一旦混掉，后面世界观和角色设定会越来越脏。

### 9.3 让 Agent 直接操作所有状态

这会让系统不可控，也很难调试。

### 9.4 把角色卡只当 prompt 文本

角色卡必须是结构化对象，不能只是一段描述文案。

## 10. 第一阶段产物建议

建议这一阶段完成后，仓库里至少有这些产物：

- `worldbook schema` 文档
- `character card schema` 文档
- `session / runtime / memory` 文档
- `game turn api` 文档
- 最小后端实现骨架
- 最小试玩入口
