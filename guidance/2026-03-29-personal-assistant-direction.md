# 2026-03-29 Personal Assistant Direction

这份文档定义项目下一阶段的产品收口方向：

- 从“多时间线互动叙事 / web-game 工作台”
- 收紧为“单用户长期陪伴的个人 AI 助手”

目标不是简单改个 UI 名字，而是重新明确：

- 什么该保留
- 什么该降级
- 什么需要大改
- 前端、后端、记忆、prompt 的主线都要怎么调整

---

## 1. 新目标：从多线叙事框架收紧成个人 AI 助手

下一阶段的产品形态不再是：

- 可以反复开很多独立 session / timeline
- 更像 galgame / interactive narrative workspace

而应该是：

- 一个持续存在的个人助手
- 有稳定人格
- 有稳定背景设定
- 有持续积累的个人记忆
- 后续可接入 RAG 与知识图谱

换句话说，产品顶层模型应该从：

- `worldbook + character + session`

逐步过渡到：

- `assistant + memory space + persistent conversation`

其中：

- `worldbook` 继续存在，但退居背景设定层
- `character card` 继续存在，但退居人格定义层
- 真正的产品主实体改成 `assistant`

---

## 2. 要保留什么

### 2.1 保留世界书，但角色从“剧情世界”改成“助手背景”

`worldbook` 依然有价值，原因是它能提供：

- 背景规则
- 地点氛围
- 人物关系底图
- 长期叙事一致性

但是它的定位要改成：

- 助手的背景设定
- 助手理解自己所处“世界”的静态底座

不再把它主要当作“多线剧情世界的舞台”。

### 2.2 保留角色卡，但角色卡是助手人格壳

`character card` 依然应该保留，用来承载：

- 性格
- 语气
- 边界
- 自我表达方式
- 披露策略

但是角色卡之后不再主要表示“剧情角色”，而是：

- 这个 AI 助手的人格设定

### 2.3 保留旁白，但旁白定位要收窄

旁白仍然可以保留，因为它能增强陪伴感和角色感。

但它不再应该被理解为：

- 叙事系统的导演层
- 游戏场景推进器

而应该变成：

- 助手表达的一层补充语义
- 动作 / 神态 / 气氛 / 内在迟疑的低频表现

也就是说：

- narration 是助手的一种表达样式
- 不是世界推进机制

---

## 3. 要降级什么

### 3.1 多独立时间线不再是产品主轴

当前的 `session rail / active / archived / 多分支时间线` 设计，适合互动叙事原型，但不适合作为个人助手的核心产品结构。

下一阶段应该把它降级为：

- 技术层快照
- 调试/回看入口
- 内部历史分段机制

而不是继续把它放在最显眼的主交互层。

### 3.2 archive 不再是“剧情线归档”

之后 `archive` 的语义应改成更偏技术层的：

- 历史阶段快照
- 记忆压缩边界
- 长期记忆沉淀时点

而不是继续当作用户心智中的“这一条故事线归档”。

### 3.3 场景目标、导演感、工作台感要整体降级

之前为了推进互动叙事，系统里保留过很多这类概念：

- scene goal
- active event
- director-like planning
- relation drawer / session workspace

这些并不是都要删除，但都要：

- 从“用户可见主交互”退回到“系统内部辅助结构”

---

## 4. 新的顶层模型

建议引入新的第一层实体：

### 4.1 `assistant`

建议未来顶层主键改为：

- `assistant_id`

并且一个 `assistant` 应该绑定：

- 一个 `worldbook`
- 一个 `character card`
- 一个长期记忆空间
- 一个用户作用域

也就是：

- `assistant = background + persona + memory`

### 4.2 `assistant conversation`

未来不再强调很多独立 `session`，而应该强调：

- 这个助手与用户之间的一条持续对话

如果内部仍然保留 session，也更适合把它理解成：

- conversation segment
- snapshot boundary
- internal storage partition

而不是产品主入口。

---

## 5. 前端必须大改

这一条非常重要：

- 前端不能只做改字眼
- 必须从“工作台 / 开局 / 分支线”思路，改成“长期助手对话”思路

### 5.1 顶层交互从 Session Workspace 改成 Assistant Workspace

当前前端的主视角还是：

- 选择世界
- 创建一局
- 在一局里推进

之后应该改成：

- 选择或创建一个助手
- 进入这个助手的持续对话
- 左侧管理助手，不是管理时间线

### 5.2 主舞台要从“开幕舞台”改成长期聊天界面

当前主舞台仍然带有强叙事感：

- 开场
- 场景
- 分支
- spotlight

下一阶段建议重构成：

- 持续聊天窗口
- 可选的旁白显示层
- 可选的记忆/资料侧栏
- 更像 personal assistant 的长期会话界面

### 5.3 SessionRail 要重做

左侧 rail 不应该继续主要展示：

- active session
- archived session
- 继续哪一局

而应该变成类似：

- assistant list
- assistant profile shortcut
- memory health / summary
- snapshots / history（次级入口）

也就是说：

- `session rail` 应逐步演化为 `assistant rail`

### 5.4 右侧关系抽屉要重命名并重构

当前“关系卡 / 长期记忆 / 时间线”的结构还带叙事产品感。

之后更适合拆成：

- 助手印象
- 最近记忆
- 重要长期主题
- 可选设定信息

甚至可以重构为：

- `Assistant Profile`
- `Memory`
- `Background`

而不是继续以“关系面板”作为核心词。

### 5.5 需要保留的前端元素

可以保留，但要换语义：

- 旁白气泡
- 长期记忆展示
- 角色摘要
- 背景设定查看

保留原因：

- 这些都能为 personal assistant 提供人格化体验

### 5.6 需要明显弱化或去除的前端元素

- “开局”心智
- 多时间线入口
- 强游戏化 session 生命周期
- 过强的舞台 / 演出 framing
- 用户把每次对话都当成新的一局

---

## 6. 后端逻辑修改方向

前端不是唯一需要大改的部分，后端逻辑也要同步收口。

### 6.1 记忆归属要改成 assistant-centric

当前长期记忆更偏：

- `worldbook_id + character_id + player_scope`

之后更合理的是：

- `assistant_id + user_scope`

原因：

- 记忆应该属于“这个助手和这个用户之间的长期关系”
- 不应该只是某个角色在某个世界里的抽象记忆池

### 6.2 session 应从主实体降级为内部边界

未来 session 更适合作为：

- 持久化分段单位
- 快照单位
- archive 压缩边界

而不是核心产品实体。

### 6.3 长期记忆要和助手深度绑定

未来每条长期记忆都应该明确绑定：

- `assistant_id`
- `user_scope`
- 可选 topic / thread / entity

而不是只跟某一局或某个 worldbook 残留耦合。

### 6.4 需要引入更明确的 memory layering

下一阶段最合理的记忆结构建议是：

1. `conversation log`
   - 原始对话日志
2. `working memory`
   - 近期 turn、当前状态、当前开放话题
3. `memory index`
   - 轻量主题索引
4. `episodic memory`
   - 具体长期事件记忆
5. `profile / semantic memory`
   - 对用户的长期印象与稳定总结
6. `knowledge graph`
   - 未来引入的实体事实层

### 6.5 retrieval 顺序也要调整

未来理想的 recall 顺序应该是：

1. 查 profile
2. 查 memory index
3. 打开最相关 topic
4. 取少量 episodic memory
5. 再混入 RAG / KG 结果

而不是一上来就：

- 直接对全部长期记忆做 top-k 搜索

---

## 7. RAG 与未来知识图谱怎么放进来

这个方向里，RAG 和 KG 不是可选装饰，而是记忆系统的重要组成部分。

### 7.1 RAG 的角色

RAG 适合承载：

- 用户上传资料
- 静态背景补充
- 世界书外部扩展知识
- 助手可引用的长期外部文本

也就是说，RAG 更适合回答：

- “资料里怎么写”
- “你之前记录过什么”
- “这个设定文本的依据是什么”

### 7.2 KG 的角色

知识图谱更适合承载：

- 实体
- 关系
- 事实稳定性
- 用户偏好 / 人际关系 / 长期约定

比如：

- 用户喜欢什么
- 助手答应过什么
- 哪些地点与哪些事件强相关
- 哪些主题和哪些情绪反应长期相关

### 7.3 三者分工

未来的混合记忆建议这样分工：

- `RAG`
  - 外部文本证据
- `episodic memory`
  - 你和助手发生过的具体事
- `profile / semantic memory`
  - 助手对你的稳定印象
- `KG`
  - 稳定事实和关系结构

---

## 8. Prompt 与生成链也要跟着收口

既然目标变成 personal assistant，那么 prompt 也不能继续保持过强的互动叙事导向。

### 8.1 要弱化的东西

- scene goal 的外显感
- 舞台推进感
- 多线叙事张力
- “这一局”的强 framing

### 8.2 要强化的东西

- 当前用户输入
- 持续关系
- 最近开放话题
- 对用户的长期印象
- 日常、真实、可持续的交流感

### 8.3 narration 的定位

之后 narration 更应该是：

- 助手人格化表达层
- 低频、可空
- 服务于陪伴感

而不是：

- 叙事说明层
- 剧情补丁层
- 强制每轮存在的装饰

---

## 9. 建议的重构顺序

建议按下面顺序推进，而不是一次性全翻：

### Phase 1：产品模型收口

- 引入 `assistant` 概念
- 明确 `worldbook` / `character card` / `memory` 的职责边界
- 把 session 从主产品心智里降级

### Phase 2：前端主交互重构

- 把 session workspace 改成 assistant workspace
- 重做左侧 rail
- 重做右侧抽屉的信息架构
- 弱化“开局 / 舞台 / 多时间线”

### Phase 3：后端记忆归属重构

- 长期记忆绑定 `assistant_id`
- profile 也绑定 `assistant_id`
- session 改成内部 segment / snapshot

### Phase 4：memory index

- 在 episodic memory 上加 topic 索引层
- 先查 index，再深入 episodic

### Phase 5：RAG + KG 融合

- RAG 负责外部文本
- KG 负责稳定事实关系
- 记忆层负责互动历史

---

## 10. 最小成功标准

如果后续只做一个高价值的方向切换里程碑，那么它应该是：

- 用户进入的不是“一局新对话”，而是“一个长期助手”
- 长期记忆明确属于某个助手
- 前端主交互不再以多时间线为核心
- 助手能在持续对话中稳定引用背景设定、角色人格和长期记忆

做到这四点，项目就会真正从“互动叙事原型”变成“有设定、有性格、有长期记忆的个人 AI 助手”。
