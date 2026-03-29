# 2026-03-29 Next Prompt

你现在接手的项目，下一阶段不应该再继续把自己理解成一个“多时间线互动叙事 web-game”。

当前最重要的方向切换是：

- 把项目收紧成一个个人 AI 助手
- 保留世界书作为背景设定
- 保留角色卡作为助手人格
- 保留 narration 作为低频人格化表达
- 用 RAG、长期记忆，以及未来知识图谱共同构建“一个助手和一个用户之间”的长期记忆空间

这意味着：

- 前端要大改
- session / timeline 的产品心智要降级
- 长期记忆的归属要改成 `assistant-centric`

---

## 当前判断

目前最重要的不是继续堆新 UI 细节，也不是先做复杂知识图谱，而是先完成产品模型收口：

- 从 `worldbook + character + session`
- 收口到 `assistant + memory + persistent conversation`

如果这一轮只做一件真正高价值的事情，那应该是：

- 明确 assistant 模型，并围绕它重构前端信息架构和后端记忆归属

---

## 第一优先级：前端主交互重构

必须明确：

- 这不是只改名字
- 而是要从 `session workspace` 变成 `assistant workspace`

### 这一轮前端最值得推进的方向

1. 左侧 rail 从“session 列表”改为“assistant 列表 / assistant 入口”
2. 主舞台从“开局/舞台/分支”改为持续聊天视角
3. 右侧抽屉从“关系卡 / 时间线”改为：
   - 助手资料
   - 长期记忆
   - 背景设定
4. archive / history / snapshots 降为次级入口
5. 减弱“新开一局”的主入口心智

---

## 第二优先级：后端模型收口

### 需要明确的新顶层实体

引入：

- `assistant_id`

并把它绑定：

- `worldbook`
- `character card`
- 长期记忆空间
- `user_scope`

### 需要调整的逻辑方向

1. 长期记忆改为绑定 `assistant_id`
2. profile 改为绑定 `assistant_id`
3. session 从主实体降为内部 segment / snapshot
4. archive 的语义改成：
   - 历史快照
   - 压缩边界
   - 记忆沉淀时点

---

## 第三优先级：记忆系统重构方向

最终要形成的结构建议是：

1. conversation log
2. working memory
3. memory index
4. episodic memory
5. profile / semantic memory
6. knowledge graph

当前这一轮先不要急着把所有层一次做完，但之后的设计必须朝这个方向对齐。

---

## 第四优先级：Prompt 与表达层收口

既然产品目标变成 personal assistant，那么 prompt 也要跟着变：

- 少一点互动叙事舞台感
- 少一点“一局”的 framing
- 多一点持续关系感
- 多一点当前互动、长期记忆和用户状态

narration 继续保留，但应该：

- 低频
- 可空
- 更像助手表达层，而不是剧情推进器

---

## 推荐的执行顺序

建议按这个顺序推进：

1. 写清 `assistant` 数据模型与边界
2. 先重做前端信息架构草图
3. 再改后端长期记忆归属
4. 再引入 memory index
5. 最后再逐步接入 KG

不要一开始就：

- 同时重做所有数据库表
- 同时重写整套 prompt
- 同时大改前后端所有命名

要先收口心智，再重构实现。
