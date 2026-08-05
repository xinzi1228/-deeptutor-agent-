# 会话交接：7 议题 brainstorming 进度 + 三模态标注拓展（2026-08-05 插播）

> 用途：压缩上下文前的状态快照。恢复后据此无缝继续。
> 状态：当前会话正在做「7 大优化议题」brainstorming（已完成 ⑤⑥③ 三份设计文档），
> 用户插播新任务「拓展为 文本/图像/视频 三模态标注」，先写规划文档，回来再继续剩余议题。

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

## 六、恢复提示词

> 读 docs/session-handoff-3modal.md + docs/superpowers/specs/ 下三份议题设计，继续标注星图。
> 当前有两条线：
> ① 7 议题 brainstorming：⑤⑥③ 已完成设计，剩余 ①②（记忆分区，已调研待写文档）、④（LS 联动）、⑦（总控）——用户可能先做「三模态标注拓展规划文档」
> ② 三模态标注拓展（文本/图像/视频）：用户将写规划文档，写完后继续此方向讨论
> 启动需 `DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001`；next build 清代理；测试基线 2985/33。
