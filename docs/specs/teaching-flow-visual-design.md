# 教学流程可视化（6 步状态图）设计

> 状态: 设计已获用户批准
> 日期: 2026-08-03

---

## 1. 背景与目标

TeachingFlowEngine 是任务级 6 步状态机（select_task→show_task→waiting→evaluate→feedback→record），状态持久化在 `data/user/workspace/learning/flow_state.json`。但**前端不可见**——教练按 6 步协议走流程，评委/学生看不到"当前走到哪一步、是否阻塞"。

**目标**：Progress 页新增「教学流程」面板——横向 6 步状态条，高亮当前步 + 显示阻塞原因，让"教学引擎按协议运行"可视化。

**来源**：差距分析 §十二④（流程状态可视化，轻量替代画布）。纯展示，不做拖拽编排。

## 2. 设计决策汇总

| # | 维度 | 决策 |
|---|------|------|
| 1 | 位置 | Progress 页「记录」Tab（与教学轨迹同 Tab，数据相关） |
| 2 | 形态 | 横向 6 步状态条（纯 CSS，无新依赖） |
| 3 | 数据 | 后端只读 flow_state.json；无文件时显示"暂无进行中的任务" |
| 4 | 后端 | `GET /api/v1/profile/teaching-flow`（读 flow_state，返回结构化的 6 步状态） |
| 5 | 无文件容错 | flow_state.json 不存在 → 空态，不报错 |

## 3. 后端 `GET /api/v1/profile/teaching-flow`

**位置**：`deeptutor/api/routers/profile.py` 新增端点

**实现**：
```python
@router.get("/teaching-flow")
async def teaching_flow_state() -> dict[str, Any]:
    """当前教学流程 6 步状态（TeachingFlowEngine flow_state.json 只读）。"""
    from deeptutor.services.teaching_flow import TeachingFlowEngine
    state = TeachingFlowEngine().get_state()
    return {
        "has_flow": bool(state.get("task_id")),
        "task_id": state.get("task_id"),
        "current_step": state.get("current_step"),
        "expert": state.get("expert"),
        "blocked": state.get("blocked"),
        "steps": state.get("steps", {}),
    }
```

- `TeachingFlowEngine().get_state()` 无文件时返回 `_fresh_state()`（task_id=None, current_step=select_task）——前端据此显示"暂无进行中的任务"
- `steps` 结构：`{step: {status, ts, f1?, readiness?}}`——前端用 status 渲染各步颜色

**测试**：`tests/api/test_profile_teaching_flow.py` — 无文件时 `has_flow=False`；有文件时返回 steps/current_step 正确。

## 4. 前端「教学流程」面板

**位置**：Progress 页「记录」Tab，放在教学轨迹上方

**组件**：`web/components/learning-stats/TeachingFlowPanel.tsx`

**渲染**：
- 横向 6 步状态条：每步一个圆点+标签（选任务/展示任务/等待提交/评测/反馈/记录）
- 状态颜色：`done` 绿、`in_progress` 蓝、`blocked` 红、`pending` 灰
- 当前步高亮 + 显示 `expert`（路由专家）
- `blocked` 时显示阻塞原因 + 建议
- 无 flow（has_flow=false）→ "暂无进行中的任务，和教练开始练习后这里会显示 6 步进度"

**数据**：`web/lib/learning-stats-api.ts` 加 `getTeachingFlow()`；Progress 页 Promise.all 加入，传入面板

**中文标签**（硬编码，页约定）：
```ts
const STEP_LABELS: Record<string, string> = {
  select_task: "选任务", show_task: "展示任务", waiting: "等待提交",
  evaluate: "评测", feedback: "反馈", record: "记录",
};
```

## 5. 测试

| 层 | 测试 |
|----|------|
| 后端 | `tests/api/test_profile_teaching_flow.py`：无文件空态、有文件结构 |
| 前端 | tsc + build |
| 冒烟 | Playwright：Progress 记录 Tab → 教学流程面板（无 flow 时空态）；对话跑一个任务后 → 6 步状态条显示当前步 |

## 6. 明确不做

- 不做拖拽编排（TeachingFlowEngine 是确定性状态机，非编辑器）
- 不做前端写 flow_state（只读展示）
- 不强制生成 demo flow_state（空态也是合理展示）

## 7. 风险

- demo 数据无 flow_state.json → 面板显示空态（合理，可后续跑任务生成）
- `get_state()` 在文件损坏时 fallback 到 fresh（已有容错）
