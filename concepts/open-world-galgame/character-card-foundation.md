# 角色卡底层逻辑设计

## 1. 目标

`character card` 不是 prompt 附件，而是角色真相对象。

它的职责是：

- 定义角色是谁
- 定义角色会怎么说话
- 定义角色知道什么、不能说什么
- 定义角色在什么场景下更容易出现
- 为关系推进、记忆写回和角色生成提供稳定锚点

一句话：

`character card` 是角色一致性的 canon source of truth。

## 2. 设计原则

### 2.1 角色设定结构化

不能只写成一段文案，至少要拆成：

- persona
- speech
- knowledge
- preferences
- constraints
- runtime hooks

### 2.2 真相与表现分离

- 真相：角色的性格、秘密、边界
- 表现：本轮说了什么、情绪如何

表现可以变，真相不能随便漂。

### 2.3 关系初值与关系状态分离

- `relationshipDefaults` 放在角色卡里
- 当前局的关系数值放在 `relationship_state` 里

### 2.4 可复用

角色卡应能在不同 worldbook 中复用一部分结构，不要绑死某个单独剧本实现。

## 3. 核心对象结构

建议角色卡至少包含以下模块。

### 3.1 Identity

- `id`
- `name`
- `age`
- `role`
- `appearanceHints`
- `tags`

### 3.2 Persona

- `personaTags`
- `coreTraits`
- `emotionalStyle`
- `socialStyle`
- `innerConflict`

### 3.3 Speech Style

- `tone`
- `verbosity`
- `habitPhrases`
- `avoidPhrases`
- `cadenceHints`

### 3.4 Knowledge Model

- `publicFacts`
- `privateFacts`
- `unlockableSecrets`
- `knowledgeBoundaries`

### 3.5 Preference Model

- `likes`
- `dislikes`
- `softSpots`
- `tabooTopics`

### 3.6 Runtime Hooks

- `scenePreferences`
- `eventHooks`
- `entryConditions`
- `exitConditions`

### 3.7 Constraint Model

- `safetyRules`
- `behaviorConstraints`
- `disclosureRules`

### 3.8 Relationship Defaults

- `trust`
- `affection`
- `tension`
- `familiarity`
- `stage`

## 4. 推荐 Schema 形态

```json
{
  "id": "lin_xi",
  "name": "林汐",
  "role": "student_archive_keeper",
  "tags": ["quiet", "observant", "guarded"],
  "personaTags": ["quiet", "observant", "guarded"],
  "coreTraits": ["细腻", "克制", "不轻易暴露脆弱"],
  "emotionalStyle": "slow_warmup",
  "socialStyle": "private_over_public",
  "innerConflict": "想靠近别人，但害怕承诺落空",
  "speechStyle": {
    "tone": "soft",
    "verbosity": "short",
    "habitPhrases": ["也许吧", "你别多想"],
    "avoidPhrases": ["高声命令", "直白威胁"]
  },
  "likes": ["旧书", "黄昏", "安静陪伴"],
  "dislikes": ["公开施压", "被逼着解释"],
  "publicFacts": ["学生会档案管理员", "经常在图书馆值班"],
  "privateFacts": ["在偷偷调查一封失踪的旧情书"],
  "unlockableSecrets": [
    {
      "id": "old_letter",
      "summary": "她调查情书失踪与自己的过去有关",
      "unlockCondition": "trust_ge_30"
    }
  ],
  "scenePreferences": ["library", "rooftop", "rainy_evening"],
  "eventHooks": ["library_after_rain", "rooftop_confession"],
  "behaviorConstraints": ["不在低信任阶段主动告白"],
  "disclosureRules": ["never reveal privateFacts before unlock"],
  "relationshipDefaults": {
    "trust": 10,
    "affection": 5,
    "tension": 0,
    "familiarity": 0,
    "stage": "stranger"
  }
}
```

## 5. 内部模块边界

### 5.1 `character_card_repository`

负责：

- 存取角色卡
- 基础查询
- 版本管理

### 5.2 `character_card_validator`

负责：

- schema 校验
- 必填字段检查
- 不合法配置检查
- worldbook 引用存在性检查

### 5.3 `character_card_normalizer`

负责：

- 标准化 tags
- 标准化 speech style 枚举
- 展平可索引字段
- 生成 persona anchor

### 5.4 `character_context_resolver`

负责：

- 根据角色卡、session state、memory 生成本轮角色上下文
- 返回给角色响应层使用

### 5.5 `character_guard_service`

负责：

- 检查秘密是否允许泄露
- 检查行为是否越界
- 检查是否违反角色边界

## 6. 角色卡与运行时的关系

必须明确区分：

- `character card`
- `relationship_state`
- `memory_profile`

### 6.1 `character card`

角色本来的设定。

例如：

- 她说话温和
- 她不喜欢公开施压
- 她知道失踪情书这件事

### 6.2 `relationship_state`

这一局当前与玩家的关系值。

例如：

- trust=34
- affection=22
- stage=warming_up

### 6.3 `memory_profile`

这一局里她如何看待玩家。

例如：

- 觉得玩家温和但不够主动
- 对某个承诺是否会兑现仍有试探

结论：

- 角色卡定义角色是谁
- 关系状态定义当前亲密程度
- 关系画像定义当前主观印象

## 7. 角色卡在运行时的用途

第一阶段至少要服务于 5 类运行时场景。

### 7.1 决定谁适合出场

导演 Agent 需要读取：

- `scenePreferences`
- `entryConditions`
- `eventHooks`

### 7.2 约束角色说话方式

角色响应层需要读取：

- `personaTags`
- `speechStyle`
- `socialStyle`
- `behaviorConstraints`

### 7.3 控制秘密揭示

角色响应层和 guard service 需要读取：

- `privateFacts`
- `unlockableSecrets`
- `disclosureRules`

### 7.4 作为记忆召回锚点

动态记忆检索可以利用：

- `characterId`
- `tags`
- `scenePreferences`
- `eventHooks`

### 7.5 作为关系推进的基准

状态更新器需要读取：

- `relationshipDefaults`
- `softSpots`
- `tabooTopics`

## 8. 复用性要求

为了后续复用，角色卡设计必须满足：

- 不依赖某个固定 UI
- 不依赖某个固定剧情线路
- 能被不同导演 Agent 复用
- 能被不同 session 反复使用

因此不建议在角色卡里直接放：

- 当前局的好感值
- 当前局已触发事件
- 当前局是否已经见过玩家
- 当前局临时情绪

这些应放在 runtime 层。

## 9. 第一阶段必须做的校验

### 9.1 基础字段校验

- `id` 唯一
- 名称不能为空
- speech style 字段类型正确
- relationship defaults 数值合法

### 9.2 引用校验

- `scenePreferences` 引用的地点在 worldbook 中存在
- `eventHooks` 引用的事件在 worldbook 或事件定义中存在

### 9.3 边界校验

- 至少有一组 `behaviorConstraints` 或 `disclosureRules`
- 至少有一组 persona / speech 锚点
- 私密信息必须带可见性规则

## 10. 对后续服务的接口建议

建议对外提供这些读取接口：

- `get_character_card(characterId)`
- `list_character_cards(worldbookId?)`
- `validate_character_card(payload, worldbookId)`
- `resolve_character_context(characterId, sessionState, memoryHints)`
- `check_character_guardrails(characterId, candidateResponse, sessionState)`

## 11. 底线原则

如果后面要继续扩展，必须始终坚持：

- 角色真相只放在 `character card`
- 当前关系只放在 `relationship_state`
- 当前印象只放在 `memory_profile`
- 角色生成只能消费角色卡，不能随意改写角色卡
- 任何秘密揭示都必须经过 guard 检查
