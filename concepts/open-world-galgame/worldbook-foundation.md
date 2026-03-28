# Worldbook 底层逻辑设计

## 1. 目标

`worldbook` 不是一份背景介绍文案，而是系统级世界真相对象。

它的职责是：

- 定义世界规则
- 定义叙事边界
- 定义地点、组织、事件种子等静态设定
- 为场景生成、角色出场、记忆召回提供统一基底

一句话：

`worldbook` 是运行时世界的 canon source of truth。

## 2. 设计原则

### 2.1 可读可写分离

- 人类编辑时可以用较友好的结构
- 系统运行时应转成标准化对象

### 2.2 设定与运行时分离

- `worldbook` 只定义静态真相
- 动态变化写到 `world_progress_state`

### 2.3 层级清晰

建议从上到下分成：

- meta
- rules
- entities
- narrative
- assets

### 2.4 面向复用

`worldbook` 不能绑死在校园题材，要支持：

- 校园
- 都市
- 奇幻
- 科幻
- 偶像
- 办公室恋爱

## 3. 核心对象结构

建议 `worldbook` 至少包含以下模块。

### 3.1 Meta

- `id`
- `version`
- `title`
- `genre`
- `tone`
- `era`
- `locale`
- `author`
- `tags`

### 3.2 World Rules

- `worldRules`
- `socialNorms`
- `hardConstraints`
- `narrativeBoundaries`

用途：

- 约束导演 Agent
- 约束角色响应
- 防止剧情越界

### 3.3 Entity Definitions

世界中的静态对象定义：

- `locations`
- `factions`
- `items`
- `globalNpcRoles`
- `relationshipArchetypes`

### 3.4 Narrative Seeds

- `eventSeeds`
- `mysterySeeds`
- `romanceArcs`
- `defaultScenePatterns`
- `timePatterns`

### 3.5 Asset Bindings

- `imageAssets`
- `mapAssets`
- `musicHints`
- `uiThemeHints`

这部分第一阶段可以只保留可选字段。

## 4. 推荐 Schema 形态

```json
{
  "id": "campus_romance_01",
  "version": "1.0.0",
  "title": "雨后的校园物语",
  "genre": ["romance", "slice_of_life", "mystery"],
  "tone": ["gentle", "melancholic", "youthful"],
  "era": "modern",
  "locale": "boarding_high_school",
  "worldRules": [
    "故事主要发生在一所封闭式寄宿高中内",
    "重要剧情通常围绕放学后和下雨天展开"
  ],
  "hardConstraints": [
    "未解锁秘密不能被角色主动泄露",
    "第一阶段不进入战斗和数值对抗玩法"
  ],
  "socialNorms": [
    "公开场合表白会引发较强情绪波动",
    "图书馆和天台更适合私密对话"
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
  "factions": [
    {
      "id": "student_union",
      "name": "学生会",
      "description": "掌握大量校内信息流"
    }
  ],
  "eventSeeds": [
    "雨天借伞",
    "失踪的情书",
    "黄昏天台的误会"
  ],
  "defaultScenePatterns": [
    "放学后在私密地点的慢节奏对话",
    "因误会而产生的情绪波动"
  ]
}
```

## 5. 内部模块边界

### 5.1 `worldbook_repository`

负责：

- 存取 worldbook
- version 管理
- 基础查询

### 5.2 `worldbook_validator`

负责：

- schema 校验
- 引用完整性检查
- 必填字段校验
- 非法值检查

### 5.3 `worldbook_normalizer`

负责：

- 默认值填充
- tag 归一化
- locale / genre / tone 枚举标准化
- 生成内部索引

### 5.4 `worldbook_query_service`

负责：

- 按地点、组织、事件种子查询世界设定
- 为场景解析和 Agent 提供读取接口

### 5.5 `world_context_resolver`

负责：

- 根据当前 session state 取最相关世界设定
- 为当前回合拼装世界上下文

## 6. worldbook 与运行时的关系

必须明确区分：

- `worldbook`
- `world_progress_state`

### 6.1 `worldbook`

表示世界本来的样子。

例如：

- 图书馆是安静、私密的地点
- 学生会掌握信息流
- 雨天容易触发慢节奏对话

### 6.2 `world_progress_state`

表示这一局当前发生了什么变化。

例如：

- 今天图书馆停电
- 天台暂时未开放
- 某个事件线已经开始

结论：

- `worldbook` 是 canon
- `world_progress_state` 是 runtime delta

## 7. worldbook 在运行时的用途

第一阶段至少要服务于 4 类运行时场景。

### 7.1 场景生成

导演 Agent 根据：

- 当前时间
- 已触发事件
- 世界规则
- 地点定义

决定当前场景。

### 7.2 角色出场约束

角色出场不是随机的，应受这些因素影响：

- 地点
- 时间段
- 社会规则
- 事件种子

### 7.3 叙事边界控制

导演 Agent 和角色响应都要读取：

- `hardConstraints`
- `narrativeBoundaries`

避免世界观崩坏。

### 7.4 记忆召回过滤

记忆召回时可以利用 worldbook 的：

- 场景标签
- 地点标签
- 事件模式

提高相关性。

## 8. 复用性要求

为了后续复用，`worldbook` 设计必须满足：

- 不依赖具体前端 UI
- 不依赖地图渲染是否存在
- 不依赖某个固定剧情模板
- 可被 AI 层、Java 产品层、管理后台共同读取

因此不建议在 `worldbook` 里直接放：

- 前端临时状态
- 玩家存档
- 好感值
- 本局已触发事件

这些都应该放在 runtime 层。

## 9. 第一阶段必须做的校验

### 9.1 基础字段校验

- `id` 唯一
- 必填字段存在
- 数组字段类型正确

### 9.2 引用校验

- `locations.id` 不重复
- `factions.id` 不重复
- 角色卡引用到的地点必须存在

### 9.3 边界校验

- `hardConstraints` 不能为空
- `narrativeBoundaries` 不能为空
- 至少有一个地点或场景锚点

## 10. 对后续服务的接口建议

建议对外提供这些读取接口：

- `get_worldbook(worldbookId)`
- `list_worldbooks()`
- `validate_worldbook(payload)`
- `resolve_world_context(worldbookId, sessionState, hints)`
- `search_worldbook_fragments(worldbookId, query)`

## 11. 底线原则

如果后面要继续扩展，必须始终坚持：

- 世界观真相只放在 `worldbook`
- 本局变化只放在 `world_progress_state`
- 场景生成只消费 worldbook，不直接改写 worldbook
- 任何 Agent 都不能把即兴发挥写回 canon
