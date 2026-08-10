# 三模态优化实现计划：AI 预标注审阅教学（借鉴 doccano-mini + labelme）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现竞赛创新点"AI 辅助标注教学"——Coach 出题时给任务附 `pre_annotation`（预标注，可能正确/含错），学生在标注台审阅修正（labelme AI 框视觉 + 一键交互），annotation_check 双评（AI 预标注 F1 vs 学生修正后 F1），Coach 反馈"你比 AI 提升多少"。借鉴 doccano-mini（few-shot LLM 预标注模式）+ labelme（AI 建议框 UX + IoU 抑制）。

**Architecture:** 数据层 task_bank 加 `pre_annotation` 字段；`get_annotation_task` 透传；标注台 iframe 读 localStorage 预置 AI 框（虚线+琥珀+可编辑+一键接受/清除）；home auto-send 附双评请求；annotation_check 双评；PERSONA 教 Coach 引导审阅。

**Tech Stack:** Python (FastAPI/LLM) + 原生 JS iframe + React。参考 clone：`%TEMP%\opencode\refs\doccano-mini\` + `%TEMP%\opencode\refs\labelme\`。

---

## 背景（已核实，grilling 定案 Q1-Q16 全默认）

- **UX 原则**：预标注不让学生困惑"该干嘛"；视觉可区分（虚线琥珀）；操作低负担（可编辑 + 一键）；反馈有激励（双评对比）。
- **LLM 可调用**：`from deeptutor.services.llm import complete`（async，delegate_expert_tool.py:247 先例）。
- **落地面**：task_bank 22 任务（图像 bbox 为主）；iframe 共享 localStorage（parent 写 `annotation_pre_annotation`，标注台 loadTask 读）；annotation_check 对任意 predictions 评分；home auto-send L709-775。
- **预标注现状**：零痕迹（greenfield）。
- **开源借鉴**：
  - doccano-mini `prompts.py`：few-shot 输出标注（NER 用 `{mention, type}` JSON）——预标注生成 prompt 模式
  - labelme `_suppression.py`：AI 建议框与已有框 IoU+containment 匹配抑制——避免 AI 框与学生框重复
  - labelme AI widget：AI 框视觉区分 + score/iou 阈值 + 批量生成 + 一键 Run

## 任务分解

### Task 1: task_bank 预标注数据（图像 bbox 打样）

**Files:**
- Modify: `data/user/workspace/task_bank.json`

- [ ] **Step 1: 选 3 个图像 bbox 任务加 `pre_annotation`**——task1（easy）/task2（medium）/task3（hard 或含错）。每任务加：
  - `pre_annotation`: 与 ground_truth 同结构的 bbox 数组
  - `pre_annotation_mode`: `"review"`（easy=正确预标注，练审阅）| `"find_error"`（hard=含错预标注，练找错）
  - `pre_annotation_note`: 给 Coach 的提示（错在哪/教学点）

> 数据原则：正确预标注 = 接近 GT 但有小偏差（框边缘差几像素）；含错预标注 = 明显错误（漏标一个目标 / 框大偏移 / 错标签），错误要"典型"有教学点。**人工精心设计**，非 LLM 生成（可控、可测、UX 佳）。

- [ ] **Step 2: 验证 JSON 合法**——`python -c "import json; json.load(open('data/user/workspace/task_bank.json', encoding='utf-8'))"`

- [ ] **Step 3: Commit**

```bash
git add -f data/user/workspace/task_bank.json
git commit -m "feat: task_bank 3 任务加 AI 预标注数据 (三模态优化)"
```

---

### Task 2: 后端透传 + 双评（get_annotation_task + annotation_check）

**Files:**
- Modify: `deeptutor/tools/task_bank_tool.py`
- Modify: `deeptutor/tools/annotation_check.py`

- [ ] **Step 1: get_annotation_task 透传**——`task_bank_tool.py` 读 task 时把 `pre_annotation`/`pre_annotation_mode`/`pre_annotation_note` 放进返回 `metadata`（不动 content markdown 结构，或加一行"本任务含 AI 预标注"提示）。读 L44-293 确认返回结构。

- [ ] **Step 2: annotation_check 双评**——`annotation_check.py` 加 `pre_annotation` 可选参数（JSON string）。当提供时：除了正常评 `predictions`（学生修正后），额外评 `pre_annotation`（AI 原预标注）→ 返回加 `pre_annotation_metrics`（同 predictions metrics 结构）+ `improvement`（学生 F1 - AI F1）。**复用 `_bbox_dict`/`_bbox_report`，零新评分逻辑。**

> 只实现图像 bbox 双评（Task 5 打样模态）。其他 task_type 传 pre_annotation 时忽略（或报错提示）。

- [ ] **Step 3: 测试**——`tests/` 新增/扩展：预标注双评（AI F1 + 学生 F1 + improvement 计算）；无 pre_annotation 时行为不变（零回归）。

```
$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_annotation_check.py -k "pre_annotation or bbox" -q
```

Expected: 全过 + 无回归。

- [ ] **Step 4: Commit**

```bash
git add deeptutor/tools/task_bank_tool.py deeptutor/tools/annotation_check.py tests/
git commit -m "feat: AI 预标注透传 + 双评 (三模态优化)"
```

---

### Task 3: 标注台 iframe 预标注审阅 UX（labelme 借鉴）

**Files:**
- Modify: `web/public/annotation_tool.html`（图像 bbox 标注台）

- [ ] **Step 1: 读预标注 + 预置 AI 框**——`loadTask()` 里读 localStorage `annotation_pre_annotation`（JSON：`{taskId, pre, mode, note}`）。匹配当前任务时：
  - 把 AI 框预置进 boxes（**标记 isAi: true**）
  - 顶部横幅显示（mode=review → "这是 AI 预标注，请审阅修正"；find_error → "这是 AI 预标注，找出它的错误"）

- [ ] **Step 2: AI 框视觉区分（labelme 借鉴）**——渲染时 `isAi` 框用**虚线边框 + 琥珀色**（区别于学生实线框），顶部小标签 "AI"。canvas 重绘逻辑判断 `isAi`。

- [ ] **Step 3: 交互（labelme suppression 借鉴）**：
  - 点击 AI 框可选中/拖动/缩放/删除（复用现有框编辑逻辑）
  - **一键"全部接受"**：所有 AI 框标为"已确认"（isAi→false，视为学生接受）
  - **一键"全部清除"**：删所有 AI 框（学生重画）
  - AI 框与手动画的新框 IoU>0.5 时提示"与 AI 框重叠"（可选，P2）

- [ ] **Step 4: 提交时带双评信息**——`askCoach()`/提交流程：把 `annotation_last_result` 附 `pre_annotation`（原始 AI 框）——home 页据此请求双评。**现有关键不变**（annotation_pending_message / annotation_last_result / 跳 /home）。

- [ ] **Step 5: 验证**——tsc（前端）+ node 语法检查 html JS。

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 6: Commit**

```bash
git add web/public/annotation_tool.html
git commit -m "feat: 标注台 AI 预标注审阅 UX (虚线琥珀+一键接受/清除) (三模态优化)"
```

---

### Task 4: home 页双评 + 反馈呈现

**Files:**
- Modify: `web/app/(workspace)/home/[[...sessionId]]/page.tsx`
- Modify: `web/components/chat/home/ChatChartCard.tsx`（若复用进度条）

- [ ] **Step 1: home auto-send 附双评**——读 `annotation_last_result` 时，若有 `pre_annotation`：POST `/api/v1/annotation/check` 带 `pre_annotation` 参数 → 响应含 `pre_annotation_metrics` + `improvement` → 拼进 enriched 消息（"AI 预标注 F1=0.62，你修正后 0.85，提升 0.23"）。

- [ ] **Step 2: 视觉对比（可选）**——若 `improvement` 存在，渲染 AI-vs-student 对比条（复用 progress 卡或简单两段条形），提升为正绿色/负灰色。**MVP：文字即可，视觉卡 P2。**

- [ ] **Step 3: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 4: Commit**

```bash
git add "web/app/(workspace)/home/[[...sessionId]]/page.tsx"
git commit -m "feat: home 预标注双评反馈 (三模态优化)"
```

---

### Task 5: PERSONA 引导审阅

**Files:**
- Modify: `deeptutor/services/persona/presets/annotation-coach/PERSONA.md`（源）+ 同步运行时副本

- [ ] **Step 1: 加规则**——教学流程节加：
  - 任务带 `pre_annotation_mode=review` → 引导"审阅 AI 预标注，确认或修正"，不是从头标注
  - `find_error` → "找出 AI 预标注的错误"，答对错误点才算掌握
  - 反馈时用双评对比（"你比 AI 提升 X"）激励
- [ ] **Step 2: 同步运行时副本**——Copy-Item 到 data/user/workspace/personas/annotation-coach/PERSONA.md

---

### Task 6: 冒烟 + review

- [ ] **Step 1: 后端测试全绿**——`python -m pytest tests/tools/test_annotation_check.py tests/api/ -q`（预存在失败除外）
- [ ] **Step 2: 前端 tsc + node 语法**——tsc + 4 个 html node --check
- [ ] **Step 3: spec review**——对照 grilling 定案（Q1-Q16 全默认）+ labelme/doccano-mini 借鉴逐项

---

## 验证
- 后端：pytest 全绿 + 无回归
- 前端：tsc + node --check
- 冒烟（可选）：Coach 出含预标注任务 → 标注台显示琥珀虚线 AI 框 → 一键接受/清除 → 提交 → home 双评对比反馈

## 提交（仅 commit，不 push）
- 按 Task 拆 4-5 个 commit。**data/ 用 git add -f**。不碰 text/audio/video 标注台（图像打样后扩展）。
