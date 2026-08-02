# 困难检测介入引擎设计文档（Struggle Detection & Intervention）

> 关联: 竞赛文件「标注星图_v5.5」模块④困难检测介入（C 角色交付物）
> 借鉴: pyBKT 状态追踪思路（不引入库，数据稀疏）、tutor-gpt Theory-of-Mind 解释层、universal-diagnostic-tutor 信号词典、Self-Improving 元模式（均已分析）
> 复用已有: readiness_gate（6 判定）、error_pattern（unconfirmed→confirmed）、foresight（预测-验证）、知识图谱 risk_path、渐进提示梯 L0-L5
> 状态: 设计稿。改代码前先对照本文件逐项验收。

---

## 1. 背景与目标

**问题**: 竞赛模块④"困难检测介入"要求"分析对话→发现卡住→主动介入"，但当前只有 prompt 层协议（decision-matrix/PERSONA），无系统级确定性检测机制。

**目标**: 新增确定性困难检测引擎——从学习记录检测学生卡住信号，生成介入建议，Coach 采纳后审计。系统主动介入，不等用户开口。

**设计原则**:
1. **确定性检测**: 信号由纯函数规则计算（连续低分/错误重复/停留超时），可单测、可重跑、可解释。
2. **复用已有信号链**: 不重复造轮子——readiness_gate 判定、error_pattern confirmed、foresight、risk_path 全部复用。
3. **LLM 仅解释层**: 检测确定，介入话术可选 LLM 生成（借鉴 tutor-gpt Theory-of-Mind），失败降级。
4. **Coach 采纳制**: 检测输出建议，由 Coach 采纳或解释（保持苏格拉底原则），不自动改难度。
5. **不引入 pyBKT**: 数据稀疏（29 技能/每技能 1-3 样本），BKT 拟合不收敛；只借鉴"每技能状态追踪"思路（stuck 计数）。

---

## 2. 架构概览

```
检测层（确定性纯函数）               介入层（工具）              审计层
┌─────────────────────────┐   ┌─────────────────────┐   ┌──────────────────┐
│ StruggleDetector         │   │  Coach 对话触发       │   │                  │
│  detect(records, now)   │──▶│  struggle_detect 工具 │──▶│ 决策审计          │
│  · 连续低分信号           │   │  → 介入建议          │   │ (log_decision)    │
│  · 错误重复信号           │   │  → LLM解释层(可选)    │   │ + 学习记录         │
│  · 停留超时信号           │   └─────────────────────┘   │ + 自改进信号        │
└─────────────────────────┘                              └──────────────────┘
        ▲ 输入: 学习记录 + error_pattern + foresight 数据
```

---

## 3. 组件拆分

### 3.1 `deeptutor/services/struggle_detector.py` — 确定性检测器（核心新服务）

**`StruggleDetector`** — 纯函数检测，无状态。

| 方法 | 签名 | 职责 |
|------|------|------|
| `detect` | `detect(*, records: list[dict], now: datetime | None = None) -> dict` | 纯函数：算全部 3 信号，输出 `{signals, has_struggle, max_severity}` |
| `low_score_streak` | `low_score_streak(records) -> list[dict]` | 连续 2 次练习 F1<0.7 → 卡住信号 |
| `repeated_error` | `repeated_error(records) -> list[dict]` | 同一 error_pattern ≥2 次 confirmed → 顽固卡住信号 |
| `stall_timeout` | `stall_timeout(records, now) -> list[dict]` | 当前任务停留 > 阈值（默认 30 分钟）→ 停留信号 |
| `intervention_suggestion` | `intervention_suggestion(signal) -> dict` | 信号 → 介入建议（对接 readiness_gate 6 判定） |

**信号结构**:
```json
{
  "type": "low_score_streak" | "repeated_error" | "stall_timeout",
  "severity": "mild" | "moderate" | "severe",
  "skill": "技能名或id",
  "task_id": "可选",
  "evidence": "证据描述",
  "count": 2,
  "ts": "ISO时间"
}
```

**3 个信号检测规则**:
| 信号 | 检测规则 | 严重度 | 借鉴来源 |
|------|---------|--------|---------|
| `low_score_streak` | 按时间序，连续 2 次练习 F1<0.7（同技能或跨技能） | moderate | readiness_gate 连续≤review 逻辑 |
| `repeated_error` | 同一 error_pattern 且 pattern_status=confirmed（≥2 次） | severe | error_pattern 升级机制 |
| `stall_timeout` | 当前任务最近记录 > 30 分钟无新记录 | mild | 渐进提示梯 L0 的 60 秒（放大到会话级） |

**确定性规则**（对齐已有 `_classify`）:
- 只读 records.jsonl，纯函数，同输入同输出
- severity 排序: severe > moderate > mild
- 无记录 → 空信号（新学生不误报）

### 3.2 `deeptutor/tools/struggle_tool.py` — `StruggleDetectTool`（Coach 工具）

- 定义: `struggle_detect(scope)` — 检测学生卡住信号 + 介入建议
- 执行流程:
  1. 读学习记录 → `StruggleDetector.detect()`
  2. 有信号 → `intervention_suggestion()` 生成建议（确定性）
  3. **severe 时** → LLM 解释层生成介入话术（借鉴 tutor-gpt Theory-of-Mind，失败降级为结构化建议）
  4. 返回 `ToolResult(content=建议文本, metadata={signals, suggestions})`
- 注册 always-on（第 14 个教学工具，含 CONFIGURABLE + BUILTIN_TOOL_TYPES）

### 3.3 接入对话（flow 协议）

- **flow-practice Step1**: 评测后调 `struggle_detect` — 检查刚评完的任务是否触发卡住信号，是则介入
- **flow-onboarding Step0**: 有历史记录分支下调 `struggle_detect` — 跨会话卡住恢复（先检测再分诊）
- PERSONA 第 12 条: 评测后/新会话开始必调 struggle_detect

### 3.4 审计闭环

- 检测到信号 → Coach 调 `log_decision(kind=struggle_intervention, target=skill, rationale=介入理由)` 审计
- 连续卡住（同技能 3 次 struggle_intervention）→ 触发 `improve_teaching_flow` 自改进信号
- 介入记录进 evaluations 或 decisions，供复盘 + 教师审计

---

## 4. 介入建议结构（对接 readiness_gate）

| 信号 | 严重度 | 介入建议 | readiness 映射 | 教学动作 |
|------|--------|---------|---------------|---------|
| 连续低分 | moderate | "task1 连续 2 次 F1<0.7，建议降到更基础任务重练" | `review_first` / `step_down` | 局部修复 / 回退前置 |
| 错误重复 | severe | "漏标模式已确认 3 次，建议换教学模式或回退 Phase1" | `diagnose_again` / `step_down` | 换角度重诊 / 强制减速 |
| 停留超时 | mild | "你在 task2 停留超过 30 分钟，需要帮助吗？" | `more_practice` / 提示梯 L0 | 主动询问 / 给提示 |

---

## 5. 数据流

1. 评测完 / 新会话开始 → Coach 调 `struggle_detect`
2. 检测器算 3 信号 → 输出 `{signals, has_struggle, max_severity}`
3. severe → LLM 解释层生成介入话术（可降级）
4. Coach 采纳或解释建议 → `log_decision(kind=struggle_intervention)` 审计
5. 连续卡住 → `improve_teaching_flow` 自改进信号

---

## 6. 错误处理与降级

| 场景 | 处理 |
|------|------|
| 无学习记录 | 返回空信号（新学生不误报） |
| 检测器内部异常 | try/except 降级为"无信号"，不阻塞教学 |
| LLM 解释失败 | 降级为结构化介入建议（检测结论仍正确） |
| 信号过多 | 只返回最高 severity 的 1-2 条，避免信息过载 |
| 同一信号重复检测 | 幂等（同输入同输出），不重复介入（有 dedup 时间窗） |

---

## 7. 测试策略

| 测试 | 验证点 |
|------|--------|
| 连续低分信号 | 构造 2 次 F1<0.7 → 触发；2 次后 1 次高分 → 不触发 |
| 错误重复信号 | 同 error_pattern confirmed → 触发；unconfirmed → 不触发 |
| 停留超时信号 | 构造超时记录 → 触发；未超时 → 不触发 |
| 确定性 | 同输入两次 detect → 输出完全一致 |
| 介入建议映射 | 3 信号 → 正确 readiness 映射 |
| 工具注册 | struggle_detect 在 always_on + schema 正确 |
| 审计写入 | log_decision(kind=struggle_intervention) 落盘 |
| 降级路径 | 无记录 / 内部异常 / LLM 失败 → 不崩溃 |
| 空记录 | 新学生 → 空信号 |

---

## 8. 与现有层的关系（不推翻原则）

- **不替换** readiness_gate / error_pattern / foresight — 全部复用为检测信号源
- **不引入 pyBKT** — 数据稀疏，只借鉴"状态追踪"思路（stuck 计数）
- **不自动改难度** — Coach 采纳制，保持苏格拉底原则
- **不新建 capability** — 保持 persona + 工具架构（渐进演进）
- **对接竞赛**: 模块④困难检测介入（C 角色交付物）核心实现

---

## 9. 明确不做（YAGNI）

- ~~引入完整 pyBKT 库~~（数据稀疏 + Windows 编译风险 + 拟合不可解释）
- ~~自动调整任务难度~~（Coach 采纳制）
- ~~LLM 全量检测~~（确定性初筛 + LLM 仅解释层）
- ~~检测 UI 面板~~（先对话内介入，面板进 future-tasks）
- ~~文本/音频标注题库~~（属③⑥子项目，非本 spec）
- ~~对话级实时检测~~（本 spec 是评测后/会话开始的检测点，非逐句流式）
