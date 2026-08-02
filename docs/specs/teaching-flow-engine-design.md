# 任务引导引擎设计（Teaching Flow Engine）

> 状态: 设计已获用户批准
> 日期: 2026-08-02

---

## 1. 背景与目标

标注星图产品中，教学流程（flow-onboarding 诊断 + flow-practice 6 步）目前是**纯协议**——靠 Coach LLM 自觉遵守 `flow-practice.md` 的步骤，无状态跟踪、无步骤 gate、无即时质量反馈。竞赛模块③「任务引导引擎」覆盖度仅 ~50%。

**本次目标**：把任务引导从"协议"升级为"引擎"——
1. **任务级 6 步状态机**（TeachingFlowEngine）：确定性跟踪 `select_task → show_task → waiting → evaluate → feedback → record`，每步有 gate（前置条件）不能跳过，阻塞时记录原因 + 下一步建议。
2. **像素级校验**：增强 `annotation_check`，无 GT 启发式检查（贴边/重叠/紧致度），评测时即时输出质量提示。
3. **题型扩展**：`grading.py` 增加判断(tf)/规范/错误案例题型（理论练习）+ task_bank 新增同类型标注任务。

**借鉴来源**：
- `chinese-thesis-workbench`（本地 skill）：**Phase+Status 两层状态模型** + `blocked_reason`/`next_action` 阻塞报告 + 用户可见 dashboard + 步骤 gate
- `1start-mathmodel`（本地 skill）：阶段工作流 + `todo.md` checklist 轻量跟踪 + 阶段边界（每阶段明确产出，不越界）
- `exampass`（本地 skill）：交互式测试 + AI 一键批改 + `kc_mastery` 掌握度
- `CAHLR/OATutor`：技能掌握状态追踪（BKT——pyBKT 已评估不引入，概念复用现有 LearningStats/knowledge_graph）
- GitHub 搜索确认：无现成「标注质量校验/教学任务状态机」开源项目——**像素校验原创**

## 2. 设计决策汇总（已确认）

| # | 维度 | 决策 |
|---|------|------|
| 1 | 引擎形态 | 后端 TeachingFlowEngine + Coach 工具（`teaching_flow`），前端不动 |
| 2 | 像素校验 | 增强 `annotation_check`（评测时并列输出启发式质量提示） |
| 3 | 题型扩展 | 两者都要：理论练习（grading.py）+ 标注任务类型（task_bank） |
| 4 | 状态机粒度 | 任务级 6 步（flow-practice） |
| 5 | 状态存储 | 独立 `flow_state.json`（`data/user/workspace/learning/`） |
| 6 | 引擎接入 | 自动推进（annotation_check 评测触发 evaluate→feedback）+ `teaching_flow` 查询工具 |
| 7 | gate 语义 | 每步骤前置条件 + 产出约束（借鉴 mathmodel 阶段边界） |
| 8 | 阻塞语义 | blocked 时记 `blocked_reason` + `next_action`（借鉴 thesis-workbench） |

## 3. 架构

```
Coach LLM ──teaching_flow 工具──→ TeachingFlowEngine
                (query/advance/reset)   │ 读/写
                                        ▼
                        learning/flow_state.json (任务级 6 步状态)
                                        ▲
annotation_check (评测) ──自动推进 evaluate→feedback──┘
task_bank 新题型(judgment/standard/error_case) ──→ annotation_check 新类型评测
grading.py 扩展(tf/规范/错误案例) ──→ 理论练习
```

## 4. TeachingFlowEngine（核心）

### 4.1 文件

`deeptutor/services/teaching_flow.py`

### 4.2 状态模型（借鉴 thesis-workbench Phase+Status）

**步骤**（任务级，flow-practice 6 步）：
```
select_task → show_task → waiting → evaluate → feedback → record
```

**步骤状态**（每步）：
| 状态 | 语义 |
|------|------|
| `pending` | 未开始 |
| `in_progress` | 进行中 |
| `blocked` | 阻塞（记 `blocked_reason` + `next_action`） |
| `needs_review` | 待学生确认（如 feedback 后学生回应） |
| `done` | 完成 |

### 4.3 Gate（前置条件 + 产出约束，借鉴 mathmodel 阶段边界）

| 步骤 | 前置（前置步骤 done） | 产出约束（推进条件） |
|------|----------------------|----------------------|
| `select_task` | 无（会话开始或上一任务 record done） | 已选 task_id |
| `show_task` | select_task done | 已展示任务 |
| `waiting` | show_task done | 学生已提交（或询问超时） |
| `evaluate` | waiting done | 已调 annotation_check（产出 F1/质量） |
| `feedback` | evaluate done | 已给出反馈 |
| `record` | feedback done | 已写 learning record |

**自动推进**：`annotation_check` 评测成功 → 引擎自动置 `evaluate` done、`feedback` in_progress。

### 4.4 状态文件结构

```json
{
  "task_id": "task1",
  "current_step": "evaluate",
  "steps": {
    "select_task": {"status": "done", "ts": "..."},
    "show_task": {"status": "done", "ts": "..."},
    "waiting": {"status": "done", "ts": "..."},
    "evaluate": {"status": "in_progress", "ts": "...", "f1": 0.5},
    "feedback": {"status": "pending"},
    "record": {"status": "pending"}
  },
  "blocked": null,
  "updated_at": "..."
}
```

### 4.5 接口（确定性、可测试）

```python
class TeachingFlowEngine:
    def get_state(self) -> dict            # 当前状态（task/step/steps/blocked）
    def start_task(self, task_id: str) -> dict      # select_task → show_task
    def advance(self, step: str) -> dict   # 推进某步（校验 gate）
    def on_evaluated(self, task_id: str, f1: float) -> dict  # annotation_check 自动调用
    def block(self, step: str, reason: str, next_action: str) -> dict
    def reset(self) -> dict                # 重置当前任务状态
    def next_step_hint(self) -> str        # 下一步建议（供 Coach 展示）
```

### 4.6 确定性原则
- 纯函数逻辑 + 文件持久化；无 LLM、无 I/O 副作用（除 flow_state.json）
- 状态推进可重跑、可测试、可审计

## 5. teaching_flow 工具

### 5.1 文件

`deeptutor/tools/teaching_flow_tool.py`

### 5.2 定义

- 名称：`teaching_flow`
- 描述：查询当前教学步骤/推进/重置，返回状态 + 下一步建议
- 参数：`action`（query/advance/reset）、`step`（推进时指定）
- 注册为 always-on 教学工具（第 15 个）
- LLM 可据此确定性遵守 flow-practice 协议

## 6. annotation_check 增强（像素级校验）

### 6.1 启发式质量检查（无 GT，纯规则）

在 `_bbox_report` 基础上新增 `_quality_checks(predictions, image_size)`：

| 规则 | 检测 | 教学提示（示例） |
|------|------|-----------------|
| `edge` 贴边 | box 与图像边界距离 < 阈值(默认 5px) | "框 {id} 贴到图像边缘，可能画过头或漏了边缘目标" |
| `overlap` 重叠 | 两 box 的 IOU > 阈值(默认 0.5) 且非嵌套 | "框 {i} 与框 {j} 高度重叠，可能重复标注同一目标" |
| `tightness` 紧致度 | 宽高比异常（>5:1 或 <1:5）或面积过大（>图像 60%） | "框 {id} 过宽/过小，可能留白过多或切到目标" |

- 输出：质量提示列表（与 IOU/F1 并列展示）+ metadata
- **自动推进**：评测后调用 `TeachingFlowEngine.on_evaluated`
- 需 `image_size`（宽高）参数——新增可选参数，缺省用较大值（如 1000×1000）或跳过 edge 检查

### 6.2 新 task_type 评测支持

`annotation_check` 新增 task_type：
- `judgment`（判断）：逐项对错判定 → accuracy
- `standard`（规范）：标注格式/规则校验（确定性：字段完整/标签合法/坐标范围）→ 合规率
- `error_case`（错误案例）：给定标注中找出错误（结合像素校验规则）→ 检出率

## 7. grading.py 扩展（理论练习题型）

`deeptutor/learning/grading.py` 在 `grade_answer` 基础上扩展：

| 题型 | 判定 |
|------|------|
| `tf`（判断） | `user.strip().lower() == expected`（布尔/对错） |
| `standard`（规范） | 确定性规则校验（复用 6.2 的规范校验函数） |
| `error_case`（错误案例） | 检出正确错误 → 正确率 |

## 8. task_bank 扩展（新标注任务类型）

`task_bank.json` 新增任务（task10-12 示例）：
- `task10`：judgment——判断标注对错
- `task11`：standard——按规范标注（格式/规则）
- `task12`：error_case——找错标注

`get_annotation_task` 支持返回新类型；`annotation_check` 支持评测。

## 9. 测试与验证

| 组件 | 测试 |
|------|------|
| TeachingFlowEngine | 状态推进/gate 校验（不能跳过）/阻塞记录/on_evaluated 自动推进/持久化/确定性/重置 |
| annotation_check 像素校验 | edge/overlap/tightness 触发 + 不触发 + 阈值参数化 |
| annotation_check 新 task_type | judgment/standard/error_case 评测确定性 |
| grading.py | tf/规范/错误案例题型判定 |
| teaching_flow 工具 | 注册 + query/advance/reset 行为 |
| 回归 | 全量 pytest + 前端 tsc（无前端改动） |

## 10. 实施任务划分（供 writing-plans 细化）

1. `TeachingFlowEngine` 服务（状态机/gate/阻塞/持久化）
2. `teaching_flow` 工具 + always-on 注册
3. `annotation_check` 像素校验增强（edge/overlap/tightness）
4. `annotation_check` 新 task_type 评测（judgment/standard/error_case）
5. `grading.py` 题型扩展（tf/规范/错误案例）
6. `task_bank` 新任务 + 接入 flow 协议 + PERSONA 更新
7. 全量回归 + 冒烟
