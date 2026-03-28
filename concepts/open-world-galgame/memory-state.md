# 记忆与状态保留方案

## 1. 目标

这份文档只回答一个问题：

“在高开放度、长会话、输入为 worldbook 和角色卡的恋爱叙事沙盒里，怎样让角色、关系和世界长期保持连续性？”

答案不是单一机制，而是一套分层系统。第一版最建议的记忆与状态模型是五层：

1. 世界观真相记忆 `world canon`
2. 角色真相记忆 `character canon`
3. 结构化运行状态 `runtime state`
4. 短期对话记忆 `recent turns`
5. 动态关系与事件记忆 `dynamic memories`

这五层必须同时存在，而且职责不能混淆。

## 2. 为什么不能只靠聊天记录

只保留原始聊天记录会出现几个问题：

- token 成本会不断增长
- 早期关键事件会被淹没
- 模型会优先相信最近措辞，而不是客观事实
- 数值关系和已触发事件无法稳定约束剧情
- 世界设定会被临场说法逐步污染

因此必须把“历史”和“真相”拆成不同类型存储，而不是一股脑地塞回上下文。

## 3. 五层记忆模型

### 3.1 第一层：世界观真相记忆 `world canon`

这是系统的最高优先级设定层，来自导入的 `worldbook`。

适合存放的内容：

- 世界规则
- 时代背景
- 组织 / 势力
- 社会禁忌
- 地点定义
- 叙事边界
- 事件种子

原则：

- `world canon` 只允许显式导入或显式编辑
- 运行时对话不能直接改写 `world canon`
- 如果剧情推进导致世界变化，应写入 `runtime state`，而不是回写 canon

### 3.2 第二层：角色真相记忆 `character canon`

这层来自角色卡，用来保证人设稳定。

适合存放的内容：

- 人设标签
- 说话风格
- 公开信息
- 私密信息
- 喜好与雷点
- 初始关系
- 行为红线
- 出场偏好和事件挂钩

原则：

- `character canon` 是角色一致性的真相源
- 模型不能因为一轮对话就改写角色设定
- 未解锁私密信息不能被越权召回给玩家

### 3.3 第三层：结构化运行状态 `runtime state`

这是“这一局当前玩到哪里”的真实状态。

适合结构化保存的内容：

- 当前场景 / 当前地点
- 当前时间段 / 日期 / 天气
- 当前在场角色
- 当前章节
- trust / affection / tension 等关系数值
- 已触发事件
- 已完成任务
- 已解锁秘密
- NPC 当前所在位置
- 世界推进标志位

这些信息建议始终保存在数据库字段或 JSON 状态对象中。

原则：

- `runtime state` 是运行时真相源
- 模型生成不能直接覆盖 `runtime state`
- 只有显式状态更新器才能修改这些值

### 3.4 第四层：短期对话记忆 `recent turns`

这层用于保持对话自然和接续感。

建议内容：

- 最近 6 到 12 轮对话
- 最近 1 到 3 次玩家行动
- 最近一次情绪变化
- 最近一次事件触发结果

用途：

- 让角色记得“刚刚说过什么”
- 保持语气和话题连续
- 支持追问、接话、吐槽、沉默等自然互动

注意：

- 这层只负责近场连续性
- 不承担长期事实保留职责
- 不应反过来覆盖 canon 或 runtime state

### 3.5 第五层：动态关系与事件记忆 `dynamic memories`

这层记录“在本次游玩中真正重要的互动节点”。

记忆单位建议为 `memory_entry`，每条都带标签。

适合存的内容：

- 第一次见面
- 第一次约会
- 第一次争吵
- 玩家做出的承诺
- 玩家失约
- 某个秘密被部分揭露
- 某次场景特殊事件
- 某角色对玩家印象发生明显变化

建议字段：

```json
{
  "id": "mem_20260326_001",
  "sessionId": "sess_01",
  "characterIds": ["lin_xi"],
  "scope": "relationship",
  "summary": "玩家答应在下雨天陪林汐去图书馆，但没有明确约定时间。",
  "emotionTags": ["warm", "uncertain"],
  "importance": 0.82,
  "recency": 0.91,
  "visibility": {
    "playerKnows": true,
    "characterKnows": true
  },
  "triggerHints": ["rain", "library", "promise"],
  "createdAt": "2026-03-26T14:20:00Z"
}
```

用途：

- 在相似场景被触发时召回
- 让角色记得过往关键事件
- 为导演 Agent 判断节奏和关系推进提供依据

## 4. 一个实用的存储模型

建议把“真相设定”“运行状态”“动态记忆”分开存。

### 4.1 Canon 对象

建议单独存：

- `worldbook`
- `character_cards`

### 4.2 Runtime State 对象

建议存在 `game_session` 主状态里：

- currentScene
- currentTimeBlock
- currentCast
- worldProgressState
- relationshipStates
- activeQuestLines
- unlockedLocations
- inventory

### 4.3 Dynamic Memory 对象

建议单独存在 `memory_entries` 集合或表里：

- relationship memories
- promise memories
- conflict memories
- scene memories
- emotion memories

### 4.4 长期画像对象

建议额外存在 `memory_profiles`：

- per-character relationship profile
- player behavior profile
- unresolved emotional threads

这样做的好处是：

- 查询简单
- 压缩方便
- 不会把 canon 和运行时记录混脏
- 可以按角色、场景、事件分别召回

## 5. 一轮交互中的读取顺序

每次玩家输入后，推荐按这个顺序组装上下文：

1. 读取 `world canon`
2. 读取 `character canon`
3. 读取 `runtime state`
4. 读取最近几轮短期对话
5. 读取当前场景相关动态记忆
6. 读取当前出场角色相关动态记忆
7. 读取高重要度的长期关系画像
8. 根据本轮输入做一次定向召回

也就是说，不是“把所有记忆都塞进去”，而是“按优先级和相关性取少量最有用的记忆”。

## 6. 一轮交互中的写回顺序

每轮结束后，不要立即把整段回复原样存档成长期记忆。

建议流程：

1. 记录原始对话日志
2. 由状态更新器更新 `runtime state`
3. 判断本轮是否产生“值得长期记住的事件”
4. 若有，生成一条或数条 `memory_entry`
5. 若触发关键节点，再刷新一次 `memory_profile`

只有满足以下条件的互动，才值得写入中长期记忆：

- 改变关系数值明显
- 解锁或关闭事件线
- 涉及承诺、失约、告白、争吵、和解
- 暴露秘密
- 明显改变角色对玩家的印象

## 7. 记忆压缩策略

开放式对话玩久了之后，动态记忆会非常多，所以必须定期压缩。

建议策略：

### 7.1 滚动摘要

每过固定回合数，例如 20 轮：

- 把其中低重要度记忆合并为一段中期摘要
- 只保留高重要度事件原子条目

### 7.2 关系画像刷新

每次关系阶段变化时：

- 重写角色对玩家的印象摘要
- 重写当前关系阶段摘要
- 更新未解决情绪线程

### 7.3 事件归档

对已结束且短期内不会再次触发的事件：

- 从高频召回层降级到归档层
- 只在相关关键词出现时再召回

## 8. 记忆召回策略

第一版可以采用混合召回：

- 规则召回
- 向量召回
- 标签过滤

### 8.1 规则召回

当输入命中明确条件时优先召回：

- 当前场景
- 当前出场角色
- 当前事件线
- 最近承诺 / 最近冲突
- 当前世界观高优先级规则

### 8.2 向量召回

当玩家说法比较自由时：

- 取玩家输入
- 拼上当前场景和角色
- 从 `memory_entry` 中召回语义相关记忆

### 8.3 标签过滤

为了避免错召回，建议按以下标签过滤：

- characterId
- locationId
- questId
- emotionTags
- visibility
- importance threshold

## 9. 记忆保真原则

为了避免“模型说过的话反过来污染真相”，要有几个硬原则：

### 9.1 Canon 和动态记录必须分开

例如：

- `world canon`: 图书馆是安静、适合私密对话的地点
- `runtime state`: 今天图书馆停电
- `dynamic memory`: 玩家在图书馆答应过陪她到闭馆

这三者不能混成同一层，否则世界会越来越脏。

### 9.2 事实和感受分开存

例如：

- 事实：玩家昨天没赴约
- 感受：林汐因此有点失望

不能把二者混成一句模糊描述，否则后续状态更新会变脏。

### 9.3 未解锁秘密不可泄露

长期记忆可以存，但召回时要经过可见性过滤。

例如：

- 玩家不知道
- 当前角色知道
- 第三人不知道

这些权限必须显式标注。

### 9.4 长期画像不能覆盖硬状态

例如“她最近开始信任你了”只是摘要，不应自动覆盖 `trust=34 -> trust=70` 这种结构化关系值。

### 9.5 Prompt 只是读取层，不是真相层

最终真相应来自：

- `world canon`
- `character canon`
- `runtime state`
- 已批准写入的 `memory entries`

而不是来自模型刚才即兴说了什么。

## 10. 建议的数据结构

第一版可以先用 JSON 存，后面再拆表。

### 10.1 Runtime Session State

```json
{
  "sessionId": "sess_01",
  "worldbookId": "campus_romance_01",
  "currentSceneId": "library_after_rain",
  "currentLocationId": "library",
  "timeBlock": "afternoon",
  "dayIndex": 4,
  "currentCast": ["lin_xi", "he_yun"],
  "worldFlags": {
    "rain_started": true,
    "rooftop_unlocked": true
  },
  "relationshipStates": {
    "lin_xi": {
      "trust": 34,
      "affection": 22,
      "tension": 8,
      "stage": "warming_up",
      "unlockedSecrets": ["old_letter"]
    }
  },
  "activeEvents": ["library_after_rain"],
  "completedEvents": ["first_meeting"]
}
```

### 10.2 Dynamic Memory Entry

```json
{
  "id": "mem_01",
  "type": "promise",
  "scope": "character",
  "characterIds": ["lin_xi"],
  "locationId": "library",
  "summary": "玩家答应会在下一次下雨时陪她待到闭馆。",
  "factPayload": {
    "promisedAction": "stay_until_close",
    "condition": "next_rain"
  },
  "emotionPayload": {
    "lin_xi": "quietly_hopeful"
  },
  "importance": 0.89,
  "visibility": {
    "player": true,
    "lin_xi": true
  }
}
```

### 10.3 Relationship Memory Profile

```json
{
  "characterId": "lin_xi",
  "playerImageSummary": "她认为玩家说话温和、愿意陪伴，但偶尔不够主动。",
  "relationshipSummary": "关系正在升温，但她对承诺是否会兑现仍保留试探。",
  "openThreads": ["next_rain_promise", "missing_letter_truth"],
  "preferredInteractionPatterns": ["gentle_reassurance", "private_conversation"],
  "avoidPatterns": ["public_pressure", "forced_confession"]
}
```

## 11. 第一版实现建议

为了尽快做出能玩的版本，建议第一版先这样做：

### 11.1 存储

- `worldbook`: JSON
- `character_cards`: JSON list
- `session_state`: JSON
- `memory_entries`: JSON list 或独立表
- `memory_profiles`: 每角色一条

### 11.2 读取

- 每次先读 canon，再读 runtime state
- 每次只取最近 8 轮对话
- 每次最多召回 3 条场景/角色相关动态记忆
- 每次最多召回 2 条高重要度长期关系画像

### 11.3 写回

- 并非每轮都写长期记忆
- 只有关键互动才写 `memory_entry`
- 每 10 到 20 轮刷新一次 `memory_profile`
- canon 默认只读，不在普通会话中被改写

### 11.4 调试

建议额外输出：

- 本轮读取了哪些 canon 与记忆
- 为什么召回这些内容
- 本轮写入了哪些新记忆
- 哪些状态字段发生变化

## 12. 最关键的一句话

如果这个项目想真正成立，记忆系统必须遵守：

“世界真相靠 world canon，角色一致性靠 character canon，当前局面靠 runtime state，近场连续性靠 recent turns，长期关系推进靠 dynamic memories。”

这几层缺一不可。
