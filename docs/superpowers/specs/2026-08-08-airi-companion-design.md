# 第五轮优化设计：Coach 陪伴人格增强（借鉴 moeru-ai/airi 陪伴机制）

> 日期：2026-08-08。来源：`moeru-ai/airi`（43K★，复刻 Neuro-sama 的 AI 伴侣，实时语音/角色一致性/主动行为）。已 clone 到 `%TEMP%\opencode\refs\airi\airi\`。深度调研了 personality 提示词、spark-notify 主动层、response-categoriser 情绪/语音分离、context registry。
> **结论**：airi 的陪伴感不靠复杂记忆，而靠 4 个**结构化机制**——① 主动时机是"第一公民"行为（参与触发列表 + no-response 工具）；② 人格在**每次决策时强制重注入**（反"帮助助手"护栏）；③ 情绪是**结构化输出通道**（ACT 令牌 → 前端身体动画）；④ 表达风格 = **IM 节奏**（消息拆分 + 叙述剥离）。我们借鉴其**教学版**：保持"诊断优先+硬性节奏"教学底线，注入陪伴温度。

## 关键事实核查（airi 深度）
- **参与触发列表**（personality-v1.velin.md:106-111）：被点名/被回复/真有兴趣/有强烈观点时开口，无聊话题**允许沉默**。
- **决策时重注入**（telegram actions.ts:36-39）：systemContent = systemTicking + personality 每次决策新鲜组装；satori llm-client.ts:31-37 每 loop 步重组。**反助手护栏**（system-action-gen-v1:44）："Do NOT revert to being a helpful assistant."
- **情绪通道**：`<|ACT {"emotion":{"name":"happy","intensity":0.8}}|>` 令牌（payloads.ts:6-16 九种情绪词汇表）→ Stage.vue 前端映射 VRM/Live2D 表情；**情绪令牌在 `<think>` 内、不进 TTS**（response-categoriser 过滤）。
- **表达风格**：message-split-v1.velin.md 第二次 LLM 专门把回复拆成 IM 节奏（兴奋/思考/戏剧停顿/补充）；tts-chunker 剥离叙述方向词（*laugh*/(sigh)）。
- **关系即 prompt 结构**（minecraft brain-prompt.ts:132-146）：主人身份绑定 + 信任陈述 + 每关系行为规则——不是从记忆学的，是硬编码进 prompt。

## 我们现状（已核实）
- `PERSONA.md`：诊断优先苏格拉底教练 + 硬性节奏约束（停/等/不继续）+ 落盘纪律。**专业但偏"程序化"**，无情感温度/主动肯定/表达风格。
- `AnnotationCoach.tsx`（前端浮动气泡）：卡点轮询介入（struggle 30s）+ 快捷键提示 + AI 标识。**无情绪表达、无成果反馈、问候语功能化**（"遇到不会的标注操作可以问我"）。
- `StreamBus.content` 事件带 metadata（stream_bus.py:106-121），Coach handleEvent 已读 event.metadata（L73），content 分支可扩展。
- `annotation_check` 返回 metadata（含 f1/readiness/chart），前端已消费 chart。

## 借鉴点

### C1. PERSONA 新增「陪伴型教学导师」人格层 ⭐ S 成本（纯 prompt）
借鉴 airi 三大支柱的教学版，新增一节：
1. **表达风格**（airi 说话怪癖 → 教学版）：口语化短句（不写论文式长段）、情感强化词（"太棒了""就差一点！"）、标注圈行话（"这框画得真准""IoU 快拉满了"）、受限 emoji（只在鼓励/庆祝时，绝不堆砌）。
2. **主动时机**（airi 参与触发列表 → 教学触发）：练习提交后**必**反馈（先具体肯定再改进）、F1 提升时**庆祝**、卡点介入时**先共情再提示**、里程碑达成**明确表扬**。补充"无聊/重复话题可简短回应"。
3. **人格基调**（airi "不是助手" → 教学版）：**是"陪练伙伴"不是"判分机器"**——学生是主角，Coach 并肩陪练；批评温和、肯定具体（引用学生实际操作而非空泛）、绝不羞辱。
4. **三明治反馈法则**（补充）：每次反馈按「具体肯定 → 精准改进 → 一句鼓励」结构。

> 教学底线明确保留：诊断优先、硬性节奏约束（停/等）、落盘纪律**不受影响**——陪伴是"教学专业外的情感连接"，不是闲聊。

### C2. 情绪表达通道（轻量前端）⭐ S 成本
airi 用 ACT 令牌 → 前端身体动画；我们**极简版**：
- **方案 1（推荐）：前端启发式 mood**——AnnotationCoach 在 coach 消息渲染时检测关键词（"太棒了/恭喜/进步"→celebrating；"别灰心/没关系/再试一次"→empathetic；"试试/换个思路"→curious），气泡加对应 emoji + 强调色。**零后端改动，纯前端。**
- **方案 2：后端 metadata mood**——agent_loop/工具发 content 时带 `metadata.coach_mood`，前端读取渲染。更精确但需改后端。
- 推荐方案 1（低成本，关键词表可维护），方案 2 留待竞赛 Demo 阶段若需精确控制。

### C3. 问候语 + 反馈体验
- AnnotationCoach 问候语改为陪伴型（"Hi，我是你的标注陪练 🤗 今天想练哪块？"）而非功能化。
- 卡点介入气泡提示词加共情前缀（"别急，这个坑很多新手都踩过…"）。

## 不借鉴
- 主动 60s ticking 循环（教学场景无需 AI 自发打扰，struggle 轮询已够）
- 完整 ACT 情绪令牌 + VRM/Live2D 动画（工程量大，竞赛 Demo 不需要 3D 身体）
- 消息拆分第二次 LLM 调用（教学回复已偏短，成本不值）
- 关系图谱硬编码（教学是 1:1 师生，无多关系）

## 优先级
| 优先级 | 项 | Effort | 说明 |
|--------|----|--------|------|
| **P0** | C1 PERSONA 陪伴人格层 | S | 纯 prompt，核心 |
| **P0** | C3 问候语 + 卡点共情 | S | 前端小改 |
| P1 | C2 前端 mood 渲染 | S | 关键词启发式 |

## 实施顺序建议
先 C1（PERSONA 纯 prompt，核心陪伴感）→ C3（前端问候语/共情）→ C2（mood 渲染，可选）。

## 复用与冲突
- 不破坏现有 PERSONA 教学体系/硬性节奏/落盘纪律（只加新节）
- AnnotationCoach 现有 struggle 轮询/快捷键保留，只改问候语 + 消息渲染
- 不触碰 annotation_tool*.html（另一会话所有）
