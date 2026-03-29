# 2026-03-28 Prompt Iteration Next Prompt

你现在接手的不是一个“先继续堆功能”的阶段，而是一个已经把长期记忆 MVP、session 生命周期、speech/narration 分离、真实 archive/recall 链路都打通过一轮的项目。

这意味着下一轮最重要的任务，不是继续主要投入 UI，也不是立刻重构数据库，而是：

- 第一优先级：提示词与对话生成链迭代
- 第二优先级：为后续性能和稳定 recall 设计记忆分层 / memory index

如果这一轮只做一件最值钱的事，就应该做第一优先级。

---

## 当前阶段判断

当前系统已经具备：

- `session -> turns -> archive -> recall` 的真实链路
- PostgreSQL 长期记忆落库：`game_memories` + `game_memory_profiles`
- turn 阶段的长期记忆读取与注入
- `speech + narration` 的前后端结构
- 对明显模板化 fallback 的第一轮收敛

但是现在真正卡体验的瓶颈，已经不是“有没有长期记忆”，而是：

- 回复有时还会过短
- narration 仍会受 persona / location 意象影响过重
- prompt 目前仍然比较密、规则感偏强
- 真实体验的好坏，越来越取决于对话生成链，而不是功能是否存在

所以接下来最重要的判断是：

- 当前最值得投入的主线应该切到 prompt iteration

---

## 第一优先级：提示词与生成链迭代

### 目标

把当前对话生成从“规则较多、偶尔僵硬、偶尔过短”推进到：

- 更像真实日常交流
- 更会顺着玩家当前输入往下接
- narration 更少、更稳、更基于现场互动
- 更少依赖本地硬规则兜底

### 这一轮应该优先做什么

#### 1. 重写 prompt 结构，而不是继续加规则

重点不是补更多禁止项，而是重组 prompt：

- 先给模型更清楚的“当前现场”
- 再给角色边界
- 再给开放话题
- 最后给少量写作要求

换句话说：

- 少做“政策说明书”
- 多做“当前情境快照”

#### 2. 让对话更多由当前互动驱动

优先级应该改成：

1. 玩家刚刚说了什么 / 做了什么
2. 角色此刻真实要回应什么
3. 当前场景气压和距离变化
4. 长期记忆里当前最相关的一条线程
5. 角色人格只做轻滤镜

不要再让这些东西主导每轮：

- 固定 signature props
- 固定语气动作
- 过多 persona 关键词
- 过强的“必须继续推进”本地检查

#### 3. narration 进一步降权

这一轮最值得试的是：

- 低压 turn 可以没有 narration
- 有明显动作 / 停顿 / 距离变化时再给 narration
- narration 应该来自这次互动，不应主要来自角色设定物件

简单说：

- narration 是补充，不是每轮必须有的风格层

#### 4. 本地门禁继续弱化

当前最大的经验之一是：

- 正常 200 返回后的本地“质量检查”太容易误杀短而自然的回答

所以下一步应该继续朝这个方向收：

- 只保留真正必要的 hard constraints
- 不再因为“太短 / 不够推进 / 不够像理想回答”就轻易改写或回退

适合保留的 hard constraints：

- 不能泄露锁定秘密
- speech / narration 不能混
- 不要出现明显 meta planning
- narration 不要重回明显重复意象

不适合再做强制替换的东西：

- 固定长度
- 固定推进力度
- 固定问句比例
- 固定表达层次

#### 5. 做 prompt A/B，而不是靠感觉继续修

下一轮最好不要再纯靠肉眼修 prompt。

至少做三组对比：

- 短 prompt vs 当前长 prompt
- narration optional vs narration default
- 轻 persona 注入 vs 重 persona 注入

测试重点不是文采，而是：

- 日常感
- 接话能力
- 不尬
- 不空
- 不复读

---

## 第二优先级：记忆分层 / memory index 设计

这个方向很重要，但应该作为 prompt 迭代之后的主线，不要抢当前第一优先级。

原因很简单：

- 现在最直接影响用户感知的是“她说得像不像人”
- 而不是“背后是不是已经有 topic index”

但这条线要尽快设计，因为它会决定下一轮性能和 recall 稳定性。

### 设计方向

新增一层轻量 `memory index`，作为长上下文的索引层。

让 turn retrieval 变成：

1. 先查 profile
2. 再查 memory index
3. 再按 index topic 深入查 episodic memory

目标：

- 降低每轮检索成本
- 减少相似旧记忆乱入
- 让 prompt 注入更像“当前线程 + 一个支撑细节”

---

## 推荐的具体执行顺序

下一轮建议严格按这个顺序推进：

1. 重写 dialogue / narration prompt 结构
2. 减少 persona props 对 narration 的影响
3. 让 narration optional
4. 弱化本地 post-check 和 fallback 触发
5. 建一个小型 prompt A/B 脚本，做 10 到 20 条真实对话回归
6. 再开始设计 `memory index` 表结构和 archive 聚类策略

---

## 这一轮不建议优先做的事

- 不建议继续先改视觉层
- 不建议先做复杂关系图
- 不建议先大改长期记忆数据库 schema
- 不建议继续堆越来越多的本地对话修正规则
- 不建议把 prompt 调优和 retrieval 重构混成同一轮大改

---

## 最小成功标准

如果下一轮只能做一个最小但高价值的里程碑，那么它应该是：

- 10 到 20 条真实对话里，明显模板 fallback 基本消失
- 日常问题能得到直接、自然、不过分文艺的回答
- narration 不是每轮都出现，但出现时更贴合当前互动
- 本地后处理不再大面积覆盖模型原答

当这几件事成立之后，再推进 memory index，收益会更稳定，也更容易判断 retrieval 真正有没有帮到生成质量。
