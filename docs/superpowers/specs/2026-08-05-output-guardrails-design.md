# 议题⑥ 设计：Agent 护栏（防大模型胡乱输出）

> 竞赛评分点：需求方案书「内容专业准确性 25 分」（输出符合行业规范、无原则性错误、关键回答有依据）+「05-伦理与安全合规性声明」c 点（设置明显"AI 生成内容"标识）。

## 1. 调研借鉴（GitHub 成熟方案）

| 来源 | 核心机制 | 融入点 |
|------|---------|--------|
| NeMo Guardrails（6.9k★） | 5 类 rails（Input/Dialog/Retrieval/Execution/Output）+ `self check facts`/`hallucination` 内建流程 | rails 分层心智模型；幻觉自检 |
| Guardrails AI（7.3k★） | Validator + OnFailAction（**拒绝/重问/修正**）+ Pydantic 结构化输出 | OnFailAction 三策略 |
| universal-diagnostic-tutor | **Guardrails 节**：绝不编造来源、Source Note Check、高利害建议边界、No Internal Leakage、不假装已验证；**QUALITY_RUBRIC** 15 维打分 | 引用真实性强制 + 离线质量评测 |
| feynman-tutor | 事实 vs 推理：缺事实直接给，不卖关子 | 无依据时明说 |
| CRAG（awesome-llm-apps 调研） | 相关性评分 → 低相关改写/明说"知识库无此内容"，不硬凑 | 检索护栏 |

## 2. 架构约束（流式，决定设计形态）

- `agent_loop` 是流式生成：每轮文本逐 chunk emit 给用户（`_emit_segments` → `stream.content`），`_finalize_finish` 拿到全量文本时用户已看到。
- **因此不能做"全量后置拦截"**（马后炮）。输出护栏必须在**工具调用阶段**（早于流式文本）完成，或靠前端/规则兜底。

## 3. 设计：三管齐下

### 3.1 `verify_output` 自检工具（核心）

- 文件：`deeptutor/tools/verify_output_tool.py`（新增 always_on 教学工具）
- **时机**：PERSONA 要求 Coach 在**关键输出**（评分结论/规范断言/知识性解释）生成前先调 `verify_output`——发生在 agent loop 工具轮，早于流式文本，不拦流式。
- 输入：`draft_answer`（草拟的最终回答）+ 可选 `claims`（关键断言）
- 输出（结构化 verdict）：
  ```json
  {
    "fabrication_leak": false,
    "role_drift": false,
    "ai_label_missing": false,
    "evidence_missing": ["目标检测遮挡阈值 50% 无规范依据"],
    "pass": true,
    "revision_advice": ""
  }
  ```
- **判定维度**：
  - `fabrication_leak`：是否编造规范/标准/成绩/来源
  - `role_drift`：是否跳出标注教练角色
  - `ai_label_missing`：是否缺 AI 生成标识
  - `evidence_missing`：关键断言（涉及规范 GB/T、标准规定、任务成绩）是否缺 `〔规范: ...〕` 引用
- **OnFailAction**：`pass` → 正常输出；检出问题 → Coach 按 `revision_advice` **修正后重出**（借鉴 NeMo self-check + OnFailAction 修正）
- 代价：仅关键输出 +1 次 LLM 调用

### 3.2 前端统一 AI 标识（合规硬性）

- `web/components/chat/home/ChatMessages.tsx` + 分享页：消息流统一显示「AI 生成内容」标识（小徽标/底部注记）
- 不依赖模型自觉，满足 05 合规 c 点

### 3.3 standards 引用强制 + 离线 QUALITY_RUBRIC

- `evidence_missing` 检测与 `standards` 引用溯源联动（parseStandardHref 已有）
- `QUALITY_RUBRIC` 精简为 6 维适配标注教学（引用真实性/无编造/角色保持/AI 标识/评分依据/教学自然度），做成离线自检脚本 `scripts/quality_audit.py`，对 trace-log 历史输出打分 → 持续改进 PERSONA

## 4. 实现与测试

- 注册 4 处（`tools/builtin/__init__.py` + always_on + PERSONA + 冒烟）
- 测试：`tests/tools/test_verify_output.py`——编造断言/角色漂移/缺引用/无标识 各样本，verdict 稳定
- 前端：AI 标识组件 + 测试
- 冒烟：让 Coach 输出含"依据 GB/T 41867"但无引用的断言 → verify_output 检出 `evidence_missing`

## 5. 衔接

- **议题⑦总控**：`verify_output` 归总控 agent 统一输出质检
- **议题⑤**：`route_input`（输入守卫）+ `verify_output`（输出守卫）构成完整 Input/Output 双闸
