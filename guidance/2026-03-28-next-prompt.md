# 2026-03-28 Next Prompt

你现在接手的已经不是单一 RAG 仓库了，而是一个包含两条主线的项目：

- RAG 主链路已经基本收口
- `web-game` 已经完成“会话工作台”第一层，包括导入设定、最近会话恢复、session 生命周期入口、active/archived 列表和 memory timeline 初版

这意味着下一轮不应该继续把主要精力放在视觉层，也不应该再回到旧的 rerank hard case 调参。新的工作范围已经明确：

- 目标：把项目推进成一个“较为长期的聊天框架”

---

## 当前判断

当前最合理的阶段判断是：

- RAG 文档问答主链路已经足够稳定
- 前端工作台已经能承接“导入 -> 开局 -> 继续最近一局 -> 归档/恢复”
- 下一步的核心瓶颈转移到了后端长期记忆，而不是 UI 或 rerank

所以这轮最值得推进的范围是：

- 长期记忆后端持久层
- session 归档沉淀
- turn 阶段长期记忆召回
- profile summary 与前端工作台联动

---

## 接下来 4 个阶段怎么推

### 1. Long Memory Storage MVP

第一优先级：

- 新增 `game_memories`
- 新增 `game_memory_profiles`
- 先不动现有文档 `docs/chunks`
- 先打通 archive promotion，再考虑 per-turn 实时入库

完成标准：

- archived session 会把重要记忆沉淀到长期表
- 每个角色有独立 profile summary

### 2. Retrieval Integration

第二优先级：

- 在 game turn 里接入 `session memory + profile memory + episodic memory`
- 保持 working memory 优先，长期记忆只召回 top-k
- 做好角色、地点、trigger、时间衰减过滤

完成标准：

- 新 session 中，角色能引用之前 session 的关键事件
- prompt 中不需要灌整段历史，也能保持连续性

### 3. Archive Summary And Compression

第三优先级：

- archive 时做记忆去重和压缩
- 把关系总结、重要事件索引、open threads 合并到 profile
- 防止长期表无限膨胀

完成标准：

- 归档一次，不只是“状态变 archived”，而是真正完成沉淀
- profile summary 比单条记忆更稳定

### 4. Workbench Observability

第四优先级：

- 前端展示 profile summary
- memory timeline 支持查看 archive 后沉淀结果
- 区分 working memory / episodic memory / semantic profile

完成标准：

- 用户和开发者都能看懂一条记忆线是怎么累积、归档、继承的

---

## 推荐的具体落地顺序

建议按下面顺序实现，而不要并行乱开：

1. 数据表和 schema
2. `archive -> long memory promotion`
3. `profile merge`
4. `turn retrieval` 接长期记忆
5. 前端显示 archive summary / profile summary
6. 再补 eval 和回归

这个顺序的好处是：

- 每一步都能独立验证
- 不会先把 prompt 改复杂，再发现没有稳定持久层

---

## 这一轮不建议优先做的事

- 不建议继续主要投入前端视觉微调
- 不建议把游戏记忆直接混入现有文档 `chunks`
- 不建议一开始就上复杂多 Agent 长期记忆编排
- 不建议先做特别复杂的情绪模拟，而没有先把记忆写入/召回链路打稳

---

## 最小里程碑定义

如果下一轮只能做一个真正有价值的里程碑，那么应该是：

- archived session 会沉淀出长期 episodic memory
- 新 session 能检索这些长期记忆
- profile summary 会跟随角色持续更新

只要这三件事成立，项目就会从“会演一局”变成“开始具备长期陪伴框架”。
