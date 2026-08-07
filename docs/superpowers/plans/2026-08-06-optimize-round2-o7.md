# 第二轮优化 P1 实现计划：O7 syllabus 进度勾选联动（MVP）

> 依据：`docs/superpowers/specs/2026-08-06-optimize-round2-design.md` O7（Bloom syllabus 进度勾选）。MVP 范围：Coach 用 `render_ui` 出能力目标进度卡（progress_card），每次任务后更新勾选；全勾由 Coach 判定触发综合评估。**不做新存储**——勾选进度天然由 learning records 推导，Coach 从 competency_map + learning records 计算数据。

## 现状
- `render_ui_tool.py` 支持 `quiz_card` / `ls_task_card`；前端 `ChatChartCard` 已支持 `progress` 类型渲染（`web/components/chat/home/ChatChartCard.tsx` L37-63，data = `{completed, total, modules:[{name,done,total}]}`）。
- competency_tree.json（能力树）+ learning records（每任务 F1）已有。
- `teaching_flow.py` 是任务级 6 步状态机（不覆盖能力目标级进度）。

## 改动

### 1. `deeptutor/tools/render_ui_tool.py` validate_component 加 `progress_card`
- 校验 data：
  - `completed` int ≥0、`total` int >0、`completed <= total`
  - `modules` list，每项 `{name: str 非空, done: int≥0, total: int>0, done<=total}`
- 返回 `{"type": "progress", "data": {...规范化...}}`（type 用 `progress` 复用前端已有渲染，不做新 chart 类型）
- `get_definition` description 加 progress_card 示例：
  `{"type":"progress_card","data":{"completed":3,"total":5,"modules":[{"name":"遮挡检测","done":1,"total":2},...]}}`

### 2. PERSONA（源 + 运行时副本同步）
`deeptutor/services/persona/presets/annotation-coach/PERSONA.md` 教学流程节（找 render_ui 相关行）追加：
- 用 `render_ui` 出能力目标进度卡（progress_card），每次标注任务评分后更新勾选（completed/total/modules 依据 competency_map 节点 + learning records 达标数）
- **全勾判定**：所有能力目标 done==total → 出综合评估任务（复用 get_annotation_task），完成后给出学习小结
同步运行时副本 `data/user/workspace/personas/annotation-coach/PERSONA.md`（SHA 校验，不 git add）。

### 3. 测试 `tests/tools/test_render_ui_tool.py` 加 4 用例
- `progress_card_valid` → success，chart.type=="progress"，data.completed==3
- `progress_card_missing_total` → fail（total 缺失/0）
- `progress_card_completed_exceeds_total` → fail
- `progress_card_bad_module` → fail（module 无 name 或 done>total）

## 验证
- `python -m pytest tests/tools/test_render_ui_tool.py -v`（旧 7 + 新 4 全过）
- 回归：`python -m pytest tests/tools/test_delegate_expert_tool.py tests/services/memory/test_bucket_paths.py -q`
- `ruff check deeptutor/tools/render_ui_tool.py`

## 提交（仅 commit）
- `feat: render_ui 支持 progress_card 能力目标进度卡 + PERSONA 教 Coach 全勾评估闭环`
