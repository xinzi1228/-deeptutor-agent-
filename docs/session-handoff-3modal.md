# 会话交接：7 议题 brainstorming 进度 + 三模态标注拓展（2026-08-05 插播）

> 用途：压缩上下文前的状态快照。恢复后据此无缝继续。
> 状态：记忆分区 Phase 2 已完成（写入分区闭环）。**Git 约定：小改动只 commit 不 push，大版本（Phase/议题）完成后统一 push**。
> 注意：另一 AI 会话正在实施三模态标注（远程 main 已有 `91f494c3` 提交），本会话的 3 个 commit 已 rebase 共存。

---

## 一、7 大优化议题进度（用户提出的，brainstorming 中）

| # | 议题 | 状态 | 已确认决策 |
|---|------|------|-----------|
| ⑤ | 输入不完整/无关处理 | ✅ 设计文档已提交 | 无关→简短回应拉回；模糊→ask_user 候选+自由输入；**独立意图分诊工具 `route_input`** |
| ⑥ | Agent 护栏 | ✅ 设计文档已提交 | **三管齐下**：`verify_output` 自检工具（关键输出前）+ 前端 AI 标识（合规 c 点）+ standards 引用强制 + QUALITY_RUBRIC 离线自检 |
| ③ | 知识库/检索/数据 | ✅ 设计文档已提交 | annotation_kb 60 篇注册为 RAG 库 + 溯源三标注 + `kb_search` 精确检索 + CRAG 相关性校验；**RAG 不升库**（已 hybrid+BM25） |
| ①② | 记忆污染+分区 | ⏸ **暂停（本次插播打断）** | 已调研完（Mem0 ADD-only+includes/excludes+metadata.topic；feynman 证据链；EverOS 遗忘）；设计：记忆区 bucket + route_input 自动归类 + L3 全局共享层。**待写设计文档** |
| ④ | Label Studio 联动 | ⏸ 未开始 | 用户设想：新手用自带标注台，有基础后 LS；生成式 UI 卡片→跳转 LS 任务；Coach 拟人化助手全程跟随；任务完退出+结果回传 LLM |
| ⑦ | 多 Agent 总控 | ⏸ 未开始 | 用户设想：总控 agent 掌管分管 agent，专人专事，避免上下文污染 |

## 二、已提交设计文档（docs/superpowers/specs/）

- `2026-08-05-input-routing-design.md`（议题⑤）
- `2026-08-05-output-guardrails-design.md`（议题⑥）
- `2026-08-05-knowledge-base-design.md`（议题③）

## 三、插播新任务：三模态标注拓展

**用户要求**：把项目拓展成 **文本 / 图像 / 视频** 三种数据类型的标注。
- 用户将先写一份**规划文档**（当前数据只有图像标注：task_bank 12 任务全图像）
- 规划文档写完后，再回来继续此方向的讨论（等用户通知）
- **相关现状**：task_bank.json（12 图像任务 5 题型）、annotation_check（IOU/F1，仅图像 bbox）、annotation-guide skill（图像标注规范）、competency_tree（AI 数据标注工程师，含文本/视频能力树节点）

## 四、项目现状（已核实）

- HEAD: `07156641`，全部推送，工作树干净（仅预存在 untracked）
- 服务：后端 8001 + 前端 3782 均在跑（之前重启过）
- 工具：always_on 21 个（系统 5 + 教学 16）
- 关键资产：task_bank（12 任务）、competency_tree、annotation-guide skill、annotation_kb（60 篇，未进 git/未注册）、start_all.bat
- 测试基线：~2985 passed / 33 预存在失败（Windows/GBK/可选依赖）

## 五、本会话调研过的 GitHub 项目（复用）

- **feynman-tutor**（koukekoukej-glitch）：意图三分类 + 事实vs推理 + 三层笔记（已 clone 到 `%TEMP%\opencode\refs\feynman-tutor`）
- **inye-adk**（iyeaaa）：intent clarification（NEVER GUESS. ALWAYS ASK.）
- **universal-diagnostic-tutor**（SenmuuuuW fork，154★）：Guardrails 节 + QUALITY_RUBRIC 15 维 + 溯源
- **universal-examprep-skill**（ZeKaiNie，263★）：溯源三标注 + 按需/全量构建
- **towardsai/ai-tutor-app**：双路 RAG + kb_shell 受限检索壳
- **NeMo Guardrails**（6.9k★）：5 类 rails + self-check
- **Guardrails AI**（7.3k★）：Validator + OnFailAction
- **Mem0**：ADD-only + scope 分区 + includes/excludes + expiration
- **MemOS/MemTensor**（10.6k★）、edumcp（已 clone）

## 六、三模态标注拓展文档（已产出，直接可用）

| 文档 | 内容 |
|------|------|
| `docs/3modal-annotation-plan.md` | **详细规划文档**（现状+设计+改动清单+注意事项+验收，供接力 AI 实施） |
| `docs/3modal-annotation-research.md` | 调研（CVAT/Doccano 范式 + task_type 跨模态矩阵 + 空白机会点） |

## 七、议题实现进度（6 议题 Phase 1 全部完成，2026-08-05 更新）

> 严格 subagent-driven-development 流程（implementer + spec/quality review），42+ 测试通过，全部推送。

| 议题 | Phase 1 实现 | 测试 | 剩余 Phase |
|------|-------------|------|-----------|
| ⑤ route_input | ✅ `route_input_tool.py`（意图分诊，confuse/off_topic 等 7 类，ask_user 联动） | 9 | — |
| ⑥ verify_output | ✅ `verify_output_tool.py`（输出质检，防编造/角色漂移/缺依据） | 8 | — |
| ③ kb_search | ✅ `kb_search_tool.py`（知识库 60 篇关键词检索）+ annotation_kb 进 git | 9 | — |
| ①② 记忆分区 | ✅ Phase 1 读取隔离 + Phase 2 consolidator bucket 写入 | 5+2 | Phase 3 完成（`/api/v1/memory/buckets` CRUD + Memory 页管理 UI，13 API 测试） |
| ④ LS 联动 | ✅ Phase 1 `ls_import_tasks` + Phase 2 `ls_task_card` 卡片跳转 | 4 | Phase 3a 完成（拟人化 Coach 浮动组件：提问走 WS / struggle 卡点介入 / 快捷键 / AI 标识）；Phase 3b/3c 见 `docs/superpowers/plans/2026-08-05-ls-annotations-workbench.md` |
| ⑦ 总控 | ✅ Phase 1 `delegate_to_expert`（专家卡委派，上下文隔离） | 7 | Phase 2 完成（独立 AgentLoop + 受限工具白名单） |

**实现计划文档**：`docs/superpowers/plans/2026-08-05-route-input.md`、`-verify-output.md`、`-kb-search.md`、`-memory-bucket-phase1.md`、`-ls-import-tool.md`、`-delegate-expert.md`

**冒烟结论**：route_input 7 类分类正确；verify_output 检出编造/角色漂移；kb_search 命中带来源；记忆区读取隔离；LS 真实建项目+导入；delegate 委派 grading_expert 正确判 advance_with_caution。

## 八、恢复提示词

> 读 docs/session-handoff-3modal.md + docs/superpowers/specs/ 下 8 份设计 + docs/superpowers/plans/ 下 15+ 份实现计划，继续标注星图。
> **Git 约定（用户 2026-08-06 重申）：小改动只 commit 不 push，每完成一个大版本（Phase/议题）再统一 push 一次。当前本地约 25 个 commit 未推送，等用户指示再 push（push 前先 fetch + rebase 远程）。**
> **优化轮次汇总**：
> ① 第二轮（Bloom/Agent_Memory_Techniques，`2026-08-06-optimize-round2-design.md` O1-O11）：O1 记忆路由 fallback / O5 专家写权限收敛 / O7 progress_card / O10 渐进加载 / O3 stale 遗忘标记 已实施；O2/O4/O6/O8/O9/O11 未做（P2）。
> ② 第三轮（DeerFlow，`2026-08-07-deerflow-borrow-design.md` E1-E8）：**E1-E8 全部完成**（subagent-driven + 两阶段 review + fix）：E1 循环检测 / E6 工具错误中文 / E2 ask_user 澄清类型化 / E4 记忆 confidence+token 预算 / E7 dangling tool call 修补 / E8 会话临时信息清洗 / E5 长会话折叠+落盘义务重注入 / E3 delegate 超时+单轮并发截断。**E3 L 部分也已完成**（`plans/2026-08-07-deerflow-e3-l.md`，4 任务全过双 review）：delegate 接入 retrieve 进度通道 + 专家进度事件 + dispatch 并行锁定 + 前端委派中文标题。**第三轮 100% 收尾**。计划：`plans/2026-08-07-deerflow-e{1..8}.md` + `e3-l.md`。
> ③ 第四轮（TencentDB-Agent-Memory，`2026-08-08-tencentdb-memory-borrow-design.md` A+B）：**A 记忆工具每轮 ≤3 次截断**（`_MEMORY_TOOLS` 6 只读工具 + `_MAX_MEMORY_TOOLS_PER_ROUND=3`，agent_loop 复用 E3 模式 + PERSONA 指南）+ **B reflect anchor-merge LLM 去重路径**（`learning_records_dedup.py`：build_candidates 锚点聚类 / parse_decisions 四动作 / apply_decision / merge_anchor_group 收敛合并，preserve pattern_confirmed + confidence 边界；reflect 失败回退规则式，truth-preserving）。**A+B 全过双 review**（65 测试）。Task 4 call_dedup_llm（真 LLM 批量决策）留 P1。参考源码 clone：`%TEMP%\opencode\refs\tencentdb-memory\`。计划：`plans/2026-08-08-tencentdb-memory-borrow.md`。
> ④ 第五轮（moeru-ai/airi 陪伴机制，`2026-08-08-airi-companion-design.md` C1-C3）：**Coach 陪伴人格增强**——C1 PERSONA 新增「陪伴型教学导师」节（表达风格口语短句/行话/受限 emoji + 主动时机练习反馈/F1庆祝/卡点共情/里程碑表扬 + 陪练伙伴基调 + 三明治反馈，教学底线保留）+ C3 AnnotationCoach 问候语陪伴化 + 卡点共情 + C2 前端 mood 检测渲染（celebrating/empathetic/curious 关键词 → emoji + 淡色强调，误报已收敛）。**C1-C3 全过双 review**。参考源码 clone：`%TEMP%\opencode\refs\airi\airi\`。计划：`plans/2026-08-08-airi-companion.md`。
> ⑤ 第六轮（NousResearch/hermes-agent 前端，`2026-08-08-hermes-frontend-design.md` H1-H3）：**AnnotationCoach 前端 UX 增强**——H2 状态环 + 瞬态情绪 flash（浮动头像 working/waiting-input/idle 环，回合完成/错误 1600ms flash，借鉴 derive_pet_state 优先级 + petFlashStore；附带补 `wait_for_input` 进 StreamEventType union）+ H3 乐观忙锁 + 忙时提示（提交同步置忙，忙时 hint 浮层防转写污染）+ H1 卡片分段渲染（handleEvent 处理 tool_result chart → cards[] 独立渲染，ChartData 导出，回合边界重置）。**H1-H3 全过双 review**。参考源码 clone：`%TEMP%\opencode\refs\hermes\hermes-agent\`。计划：`plans/2026-08-08-hermes-frontend.md`。
> 当前两条线：
> ① 7 议题：⑤⑥③ 彻底完成；①② Phase 1-3 全完成；④ Phase 1-2 + 3a + **3b + 3c 完成**；⑦ Phase 1-2 完成。**④ 3b 前端反馈接入也完成**（`plans/2026-08-05-ls-annotations-3b-feedback.md`，无侵入 iframe）：新增 `GET /api/v1/annotation/ground-truth/{task_id}` 端点（task_bank 键即任务 id）+ home 页读 `annotation_last_result`（iframe 既有 localStorage 桥接）→ 评分端点二次评分 → `AnnotationResultCard` 渲染即时评分卡 + 增强 Coach 消息。剩余：竞赛交付材料（9/1）。`④ 3b 前端接入依赖的 iframe 桥接已存在（iframe 提交写 localStorage + 跳 /home，home 页 30s 内 auto-send 给 Coach），全程未碰 annotation_tool*.html`。
> ② **三模态标注拓展**：`docs/3modal-annotation-plan.md` + `research.md`；另一会话实施中（远程已有提交）。
> 启动：`start_all.bat`（后端 8001 + 前端 3782 + LS 8080 均在跑）；前端需 `DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001`；next build 前清 `HTTP_PROXY/HTTPS_PROXY`；PowerShell 设 `PYTHONIOENCODING=utf-8`。测试基线 2985/33（GBK/可选依赖）。
