# 2026-03-29 Assistant Phase 1 Implementation

这份文档把本轮要推进的第一阶段工作收成一个可执行落地稿，目标是：

- 不再继续发散成多时间线互动叙事产品
- 先把顶层心智收口到 `assistant`
- 前端先切成 assistant workspace
- 后端先定义 assistant-centric 归属方向
- 保留 `session` 兼容层，不粗暴删除旧逻辑

---

## 1. 第一阶段实施计划

### Phase 1A：定义 assistant 模型与兼容映射

本阶段先落文档和类型草案，不急着全量改表或重写 API。

执行项：

1. 增加 `assistant` 数据模型草案
2. 写清 `assistant -> worldbook / character / memory / session` 的映射
3. 前端先使用 projection / adapter 把现有数据投影成 assistant 视角
4. 后端先补 schema 草案，为后续真正引入 `assistants` 存储做准备

完成标准：

- 有清晰 assistant 字段定义
- 有兼容映射规则
- 前后端代码里都能看到 assistant draft 类型

### Phase 1B：前端信息架构切到 assistant workspace

本阶段不改底层 session 存储，而是先改主界面的组织方式。

执行项：

1. 左侧主入口改成 assistant rail
2. 中间主舞台改成 persistent conversation panel
3. 右侧抽屉改成 assistant profile / memory / background
4. session snapshots 降级为次级入口
5. 把“开局 / 第一幕 / 舞台 / 分支线”这类文案整体降级

完成标准：

- 主界面第一眼是“个人助手”
- session 仍可工作，但不再占据产品心智中心

### Phase 1C：后端 assistant-centric 记忆迁移设计

本阶段先给迁移方案，不在本轮一次性改完。

执行项：

1. 把长期记忆未来归属明确为 `assistant_id + user_scope`
2. 把 `worldbook`、`character`、`session` 的旧归属说明改成兼容层
3. 保留 session 作为 conversation segment / snapshot
4. 为后续 assistant API 预留字段与服务入口

完成标准：

- 后续可无痛从 `worldbook + character + session` 迁到 `assistant + memory`

---

## 2. Assistant 模型草案

### 2.1 核心定义

`assistant = background + persona + memory + user_scope`

也就是：

- `worldbook` 提供背景设定
- `character card` 提供人格壳
- 长期记忆/RAG/KG 共同组成 assistant-centric 记忆空间
- `session` 只保留为内部对话片段和快照边界

### 2.2 推荐字段

```ts
type AssistantStatus = 'draft' | 'active' | 'archived';

interface Assistant {
  id: string;
  name: string;
  worldbookId: string;
  characterId: string;
  userScope: string;
  status: AssistantStatus;
  memoryStatus: 'empty' | 'building' | 'ready';
  summary: string;
  createdAt: string;
  updatedAt: string;
}
```

建议补充的扩展字段：

- `avatar`
- `pinnedSessionId`
- `lastInteractionAt`
- `memoryStats`
- `profileVersion`

### 2.3 与旧模型的映射

#### 旧对象新定位

- `worldbook`
  - 助手背景设定
- `character`
  - 助手人格定义
- `session`
  - conversation segment / snapshot boundary

#### 兼容映射规则

短期内允许前端把当前数据投影成 assistant：

- 一个 `character card` 暂时可投影成一个 assistant draft
- `worldbookId` 直接作为 assistant 的背景引用
- `characterId` 直接作为 assistant 的人格引用
- 与该 `characterId` 相关的 session 作为该 assistant 的历史快照

这个 projection 只是过渡层，不是最终存储模型。

---

## 3. 前端信息架构改造方案

### 3.1 顶层结构

建议主界面改成：

1. 左侧：`AssistantRail`
2. 中间：`AssistantConversation`
3. 右侧：`AssistantDrawer`

### 3.2 左侧 Assistant Rail

主职责：

- assistant list
- 当前助手入口
- 助手人格和背景摘要
- session snapshots/history 次级入口

建议区块：

1. 当前助手 / 最近对话入口
2. Assistant list
3. Background 设定摘要
4. Persona / supporting cast 摘要
5. Conversation snapshots

### 3.3 中间 Persistent Conversation

主职责：

- 展示用户与助手的持续对话
- narration 作为低频表达层
- scene/location 退到轻上下文

建议变化：

- `DialogueStage` 心智改成持续会话窗口
- `TurnSpotlight` 改成当前回应聚焦
- 底部输入区改成“给助手发送消息”

### 3.4 右侧 Assistant Drawer

主职责：

- Assistant Profile
- Working memory / recent memories
- Long-term memory
- Background context

建议变化：

- 关系卡不再做主角
- timeline 不再做产品主心智
- scene shift 只保留为补充上下文

---

## 4. 后端长期记忆迁移方向

### 当前状态

当前长期记忆主要仍围绕：

- `worldbookId`
- `characterIds`
- `sessionId`

### 目标状态

未来应逐步迁到：

```ts
assistant_id + user_scope + memory_type
```

建议结构：

1. `conversation_log`
2. `working_memory`
3. `memory_index`
4. `episodic_memory`
5. `profile_memory`
6. `knowledge_graph`

### 兼容策略

迁移期内：

- session 继续存在
- archive 继续可用
- 但语义改成快照/沉淀边界
- 新逻辑优先围绕 `assistant_id`

---

## 5. 需要改动的主要文件和模块

### 前端

- `web-game/src/App.tsx`
  - 顶层状态、文案、workspace 入口改成 assistant 视角
- `web-game/src/lib/types.ts`
  - 增加 assistant draft 类型
- `web-game/src/lib/assistantWorkspace.ts`
  - 新增 assistant projection / local memory adapter
- `web-game/src/components/AssistantRail.tsx`
  - 新增 assistant-centric 左侧入口
- `web-game/src/components/DialogueStage.tsx`
  - 改成 persistent conversation 文案
- `web-game/src/components/SceneInspector.tsx`
  - 改成 assistant profile / memory / background 组织
- `web-game/src/components/TurnSpotlight.tsx`
  - 改成当前回应聚焦
- `web-game/src/components/WorldbookPreview.tsx`
  - 改成背景设定预览
- `web-game/src/components/SessionComposerModal.tsx`
  - 改成“开启助手对话片段”的文案

### 后端

- `python-ai/app/models/game_schemas.py`
  - 增加 assistant schema 草案
- `python-ai/app/services/game_session_service.py`
  - 后续把 session 的 product role 降级为 conversation segment
- `python-ai/app/services/long_memory_service.py`
  - 后续把长期记忆主归属从 `worldbook + character` 收口到 `assistant`
- `python-ai/app/routers/game.py`
  - 后续新增 assistant API
- `python-ai/app/services/game_storage_service.py`
  - 后续新增 `assistants` 存储目录或表

---

## 当前阶段补充判断（前端完整链路测试）

当前第一阶段已经不只是在 UI 上切成 assistant workspace，还需要把前端主验收升级为完整助手链路测试：

- 左侧允许把 projected assistant 显式固化成真实 `assistant`
- 新建对话片段必须默认从真实 assistant 入口进入
- Playwright 主回归从旧 `session-workspace` 脚本升级为 `assistant-workspace` 全链路脚本
- session / snapshot 保留为兼容层，但只作为 assistant 下的次级历史入口

---

## 6. 本轮最小实现建议

本轮适合直接落地的最小改动：

1. 新增 assistant draft 类型
2. 前端增加 assistant projection / workspace adapter
3. 左侧 rail 改成 assistant 主入口
4. 中间和右侧切成 assistant-centric 文案与信息结构
5. 保留现有 session API 和存储逻辑不变

这能先完成“产品心智收口”，同时把后续真正的数据迁移风险压低。
