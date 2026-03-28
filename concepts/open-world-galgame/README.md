# 高开放度 Galgame / 恋爱叙事沙盒设计草案

## 1. 项目定位

这个方向不是传统线性 galgame，而是一个基于现有 RAG + rerank + agent 能力构建的“高开放度恋爱叙事沙盒”。

第一版的系统输入建议收敛为两类：

- 世界观设定 `worldbook`
- 角色卡 `character cards`

玩家可以：

- 导入一个世界观
- 导入多张角色卡
- 在世界观约束下进入动态生成的场景
- 与角色实时对话
- 推进关系、事件和支线
- 通过长期互动形成持续变化的剧情

这里的“地图”不是系统的唯一核心输入，而应该成为世界观里的一个可选子结构，例如 `locations` 或视觉地图资源。

一句话版本：

“一个基于 worldbook 和角色卡驱动、支持持续记忆与动态剧情推进的 Agentic 恋爱叙事引擎。”

## 2. 为什么这样更合理

如果把“地图”当成第一版的核心输入，系统会天然偏向“节点移动游戏”；但高开放度恋爱叙事真正需要稳定的是：

- 世界规则
- 角色一致性
- 场景生成逻辑
- 长期关系与记忆

因此第一版更合理的抽象是：

- `worldbook` 负责定义世界怎么运转
- `character card` 负责定义角色是谁
- `session state` 负责记录当前玩到哪里
- `agent` 负责在这些约束下组织场景和互动

这样做也更泛化：

- 不只适用于校园恋爱
- 也适用于都市、奇幻、偶像、办公室、末世等世界观

## 3. 为什么适合当前仓库

现有仓库已经具备几个关键底座：

- 文档导入、切块、检索、rerank
- query planning 和 retrieval orchestration
- refusal、citation、decision summary、debug traces

这些能力映射到新产品之后可以变成：

- `worldbook` -> 世界设定、规则、地点、组织、事件种子
- `character cards` -> 人设、秘密、说话风格、关系初值、行为边界
- `memory retrieval` -> 召回角色记忆、关系记忆、世界设定依据
- `rerank` -> 在大量设定与记忆中筛出当前最相关内容
- `agent` -> 决定当前场景、出场角色、事件推进和节奏控制

因此这个方向不需要推翻现有系统，而是在其上增加“叙事状态层”和“导演调度层”。

## 4. 产品目标

第一版的目标不是做成无限开放世界，而是做成“高自由输入 + 受控剧情推进”的在线网页产品。

第一版应满足：

- 支持单人游玩
- 支持网页实时聊天
- 支持导入一个结构化 `worldbook`
- 支持导入多张结构化角色卡
- 支持动态生成场景
- 支持持续的关系变化和事件解锁
- 支持保存 / 恢复游戏进度
- 支持 Agent 作为导演统一调度剧情

第一版不应追求：

- 多 Agent 自由自治
- 全世界实体都长期独立模拟
- 完全无边界的开放剧情
- 复杂战斗、经济、养成大系统

## 5. 核心玩法循环

建议的核心循环如下：

1. 玩家进入当前会话
2. Agent 读取 `worldbook`、角色卡、当前 session state 和记忆状态
3. Agent 决定当前场景、可见角色、可触发事件和对话基调
4. 玩家自由输入或选择行动
5. Agent 调用现有 RAG 检索相关设定和记忆
6. Agent 生成角色回应、场景推进和状态变更
7. 系统保存新的世界推进状态和关系状态
8. 下一回合继续

这个循环的重点是：

- 玩家可以自由表达
- 角色不会失忆
- 场景来自统一世界观，而不是临场乱编
- 剧情推进依赖状态，而不是单次对话

## 6. Agent 的职责边界

Agent 在这个产品中不是“直接扮演所有角色的万能聊天模型”，而是一个导演层。

建议拆成两个逻辑层：

### 6.1 导演 Agent

导演 Agent 负责：

- 判断当前场景的叙事目标
- 决定哪些角色应该出场
- 决定本轮是否触发事件、冲突、约会、误会、秘密揭示
- 为角色回复提供场景约束
- 保证世界观和叙事节奏不发散

### 6.2 角色响应层

角色响应层负责：

- 基于角色卡和当前状态生成符合人设的回应
- 引用角色长期记忆、短期记忆和场景上下文
- 不越权泄露未解锁秘密

第一版可以先把“导演 Agent + 单模型角色响应”放在一个服务里，不必真的拆成多个 agent 进程。

## 7. 世界观导入设计

第一版建议把核心输入从“地图”改成“世界观设定”。

`worldbook` 应至少包含：

- 世界名称
- 题材与基调
- 时代背景
- 世界规则
- 社会规则 / 禁忌
- 组织 / 势力
- 地点集合
- 可触发事件种子
- 叙事边界
- 风格指引

示例字段：

```json
{
  "id": "campus_romance_01",
  "title": "雨后的校园物语",
  "genre": ["romance", "slice_of_life", "mystery"],
  "tone": ["gentle", "melancholic", "youthful"],
  "era": "modern",
  "worldRules": [
    "故事主要发生在一所封闭式寄宿高中内",
    "重要剧情通常围绕放学后和下雨天展开",
    "未解锁秘密不能被角色主动越权透露"
  ],
  "socialNorms": [
    "公开场合表白会引发较强情绪波动",
    "图书馆和天台更适合私密对话"
  ],
  "factions": [
    {"id": "student_union", "name": "学生会", "description": "掌握大量校内信息流"}
  ],
  "locations": [
    {
      "id": "library",
      "name": "图书馆",
      "description": "安静、偏私密，适合慢节奏对话和秘密交换。",
      "tags": ["quiet", "study", "romance"],
      "sceneHints": ["rain", "after_school", "shared_book"]
    }
  ],
  "eventSeeds": [
    "雨天借伞",
    "失踪的情书",
    "黄昏天台的误会"
  ],
  "narrativeBoundaries": [
    "不进入硬核战斗系统",
    "核心体验是关系推进与情绪互动"
  ]
}
```

说明：

- `locations` 仍然重要，但它是世界观的一部分，而不是系统唯一输入
- 后续如果要做可视地图，可以把图片资源和地点节点挂在 `worldbook.locations` 上

## 8. 角色卡导入设计

角色卡必须结构化，不要只是一段自然语言简介。

建议字段：

- 基础信息：姓名、年龄、身份、外观关键词
- 说话风格：语气、长度、口头禅、禁忌表达
- 性格标签：内向、强势、疏离、温柔等
- 偏好和雷点
- 公开信息
- 私密信息
- 初始关系
- 出场条件
- 场景偏好
- 触发事件条件
- 红线约束

示例字段：

```json
{
  "id": "lin_xi",
  "name": "林汐",
  "personaTags": ["quiet", "observant", "guarded"],
  "speechStyle": {
    "tone": "soft",
    "verbosity": "short",
    "habitPhrases": ["也许吧", "你别多想"]
  },
  "likes": ["old books", "sunset", "small promises"],
  "dislikes": ["public pressure", "being forced to explain"],
  "publicFacts": ["学生会档案管理员", "经常在图书馆值班"],
  "privateFacts": ["在偷偷调查一封失踪的旧情书"],
  "relationshipDefaults": {
    "trust": 10,
    "affection": 5,
    "tension": 0
  },
  "scenePreferences": ["library", "rooftop", "rainy_evening"],
  "eventHooks": ["library_after_rain", "rooftop_confession"],
  "safetyRules": ["never reveal privateFacts before unlock"]
}
```

## 9. 状态系统设计

这是整个项目最重要的部分。高开放度不是靠“模型多自由”，而是靠“状态一直连续”。

建议把系统分成五层：

### 9.1 世界观真相层

这是导入后的 `worldbook canon`，例如：

- 世界规则
- 组织和地点定义
- 叙事边界
- 事件种子

这一层是最高优先级设定，不应该被运行时对话污染。

### 9.2 角色真相层

这是角色卡定义的 `character canon`，例如：

- 人设
- 公开 / 私密信息
- 说话风格
- 行为边界
- 初始关系

这一层也不应被模型临场改写。

### 9.3 会话运行状态

当前这一次游玩的即时状态：

- 当前章节
- 当前时间段
- 当前场景
- 最近行动
- 当前在场角色
- 最近对话主题

### 9.4 关系与世界推进状态

面向本次游玩的动态变化：

- trust / affection / tension
- 已解锁秘密
- 已触发事件
- 已完成支线
- 当前悬念列表
- 世界中的时间、天气、人物位置变化

### 9.5 记忆状态

面向叙事一致性的历史记忆：

- 玩家曾说过什么关键承诺
- 玩家和角色之间发生过哪些关键节点
- 哪些误会、冲突、和解已经发生
- 哪些重要信息是“玩家知道但角色不知道”
- 哪些重要信息是“角色知道但玩家还没解锁”

## 10. 记忆与状态保留总原则

这一块决定产品能不能成立。

原则只有一条：

“不要把持续记忆寄希望于对话历史本身，而要把记忆做成 canon 设定 + 结构化状态 + 可检索记忆摘要的混合系统。”

也就是说，不能只把整段聊天记录不断塞给模型。那样会导致：

- 上下文爆炸
- 记忆漂移
- 角色忘事
- 世界设定被临场措辞覆盖

正确方式应该是分层组合：

- `world canon`: 世界观真相
- `character canon`: 角色卡真相
- `structured runtime state`: 当前运行状态
- `dynamic memories`: 关系和事件记忆
- `recent turns`: 最近几轮真实对话

详细方案见同目录下的 `memory-state.md`。

## 11. 建议的后端架构

在现有仓库基础上，建议新增一层游戏服务，而不是改坏现有 RAG 主链路。

建议新增模块：

- `worldbook_service`
- `character_card_service`
- `game_session_service`
- `game_state_service`
- `agent_director_service`
- `character_response_service`
- `memory_service`

建议的数据对象：

- worldbook
- location_definition
- character_profile
- game_session
- scene_state
- relationship_state
- world_progress_state
- memory_entry
- event_definition

## 12. 一次请求的建议执行流程

玩家每发一条消息，后端流程可以是：

1. 读取当前 `game session`
2. 读取 `worldbook canon` 和角色卡 canon
3. 读取 scene/world/relationship runtime state
4. 取最近几轮短期对话
5. 召回当前场景、当前角色、相关长期记忆
6. 导演 Agent 判断：
   - 本轮场景目标是什么
   - 本轮谁回应
   - 是否触发事件
7. 角色响应层生成回复
8. 状态更新器写入：
   - 数值变化
   - 事件解锁
   - 新记忆
   - 场景变化
9. 返回给前端：
   - 对话内容
   - 状态变化
   - 可见角色变化
   - 新解锁事件或场景线索

## 13. 网页产品形态

这个方向很适合在线网页，第一版页面建议如下：

### 13.1 主页面

- 左侧：当前场景 / 世界观摘要 / 可切换地点
- 中间：聊天与叙事流
- 右侧：角色卡、关系状态、线索、任务
- 顶部：时间、天气、日期、当前章节

### 13.2 管理页面

- 导入 `worldbook` JSON
- 导入角色卡 JSON
- 查看事件定义
- 查看 session 存档

### 13.3 调试页面

基于你现有 observability，额外展示：

- 本轮导演 Agent 目标
- 召回的记忆条目
- 本轮触发的事件判定
- 状态 diff
- 当前引用了哪些世界观设定 / 角色卡设定

## 14. 第一版建议范围

为了快速做出可玩的东西，第一版建议限制为：

- 单人
- 单个 `worldbook`
- 3 到 5 个角色
- 1 条主线
- 3 到 8 条支线
- 2 到 3 个核心关系维度
- 结构化导入
- 单导演 Agent

这一版的成功标准是：

- 角色不明显失忆
- 场景切换和事件触发有反馈
- 好感 / 信任 / tension 变化合理
- 玩家感觉“世界在记住我做过的事”

## 15. 最大风险

### 15.1 角色人设漂移

解决方向：

- 角色卡结构化
- 角色响应前强制召回 persona anchor
- 对高优先级设定加硬约束

### 15.2 世界观被运行时污染

解决方向：

- `worldbook canon` 单独存储
- 运行时回复不能直接改写 canon
- 世界推进只能写入 runtime state

### 15.3 剧情无边界发散

解决方向：

- 由导演 Agent 统一给出场景目标
- 事件触发依赖状态机，不靠模型临场发挥

### 15.4 记忆混乱

解决方向：

- canon、runtime state、dynamic memory 分层保存
- 短期窗口只保留最近若干轮
- 长期关系记忆定期压缩

## 16. 下一步最值得做的事情

如果决定继续推进，我建议按这个顺序做：

1. 先定义 `worldbook schema`
2. 再定义 `character card schema`
3. 再定义 `game session / runtime state / memory` 的持久化结构
4. 最后才是 Agent prompt 和网页 UI

原因很简单：

这个项目最难的不是“让模型说话”，而是“让世界一直成立”。

而世界是否成立，几乎完全取决于设定层、状态层和记忆层是否设计正确。


## 17. 补充设计文档

- phase-1-plan.md: 第一阶段任务清单与实现顺序
- worldbook-foundation.md: 世界观底层逻辑与模块边界
- character-card-foundation.md: 角色卡底层逻辑与模块边界

