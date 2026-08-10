# 第二轮优化实现计划：O8 行内思维快照（标注台"这里有疑问"按钮 + Coach 优先）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 标注台支持学生**随时**标记"这里有疑问"（不必等提交），Coach 优先回应。借鉴 Bloom `???`（用户在文档中即时疑问，优先级高于文末反馈）。

**Architecture:** 4 个 `annotation_tool*.html` 各加"疑问"按钮（`askDoubt()`，默认可见，存 localStorage 疑问标记 + 当前任务上下文）→ home 页 auto-send 识别疑问标记 → 消息带优先级提示 → Coach（PERSONA）优先回应。

**Tech Stack:** 原生 JS（iframe html）+ React（home 页）+ PERSONA。

---

## 背景（已核实）

- 4 个标注台：`web/public/annotation_tool.html`（bbox，425 行）、`_text.html`（实体）、`_audio.html`（音频）、`_video.html`（视频）。结构一致：`btnCoach` 按钮（L71-78，`display:none` 提交后才显示）+ `askCoach()`（L297 起）+ `currentTask` + `checkResult` + TASKS。
- `askCoach()` 机制：拼结构化消息 → `localStorage.setItem('annotation_pending_message', msg)` + `annotation_pending_time` → 跳 `/home`。
- home 页 auto-send（`web/app/(workspace)/home/[[...sessionId]]/page.tsx:715-768`）：30s 内读 `annotation_pending_message` → 读 `annotation_last_result` 调评分端点 → `sendMessage(enriched)`。
- **现状缺口**：疑问只能等提交后点"问Coach"，且消息无优先级区分——Coach 无法知道这是即时疑问 vs 结果分析。

## 任务分解

### Task 1: 4 个标注台加"疑问"按钮 + askDoubt()

**Files:**
- Modify: `web/public/annotation_tool.html`、`annotation_tool_text.html`、`annotation_tool_audio.html`、`annotation_tool_video.html`

- [ ] **Step 1: 加按钮**——在 `btnCoach` 旁（同 toolbar/容器）加疑问按钮，**默认可见**（不依赖提交）：

```html
<button class="coach" id="btnDoubt" onclick="askDoubt()">这里有疑问</button>
```

> 位置：紧跟 `btnCoach` 的兄弟元素。样式复用 `.coach` 类（读各文件 .coach 定义，可能需微调色区分疑问=琥珀 vs 分析=主色）。

- [ ] **Step 2: 加 askDoubt() 函数**——`askCoach()` 旁加：

```js
// ── Ask Doubt (O8 行内思维快照) ──
// 学生随时标记"这里有疑问"，不必等提交；Coach 优先回应。
function askDoubt() {
  const t = TASKS[currentTask];
  const hasResult = !!checkResult;
  let msg = `⚠ 我有疑问（进行中提问）：「${t.desc.split('—')[0]}」标注练习里，`;
  msg += hasResult
    ? `刚才提交的结果 F1=${(checkResult.f1*100).toFixed(0)}%，但我在以下地方没把握：\n`
    : `我还没提交，但做到这里不确定，想先确认一下：\n`;
  msg += `- 当前任务: ${currentTask}\n- 我画/标的内容: ${JSON.stringify(boxes || entities || segments || taskGroup || [])}\n`;
  msg += `请先解答我的疑问，再告诉我怎么继续。`;

  localStorage.setItem('annotation_pending_message', msg);
  localStorage.setItem('annotation_pending_time', String(Date.now()));
  localStorage.setItem('annotation_doubt', '1');  // O8: 疑问标记 → 优先回应
  if (checkResult) {
    localStorage.setItem('annotation_last_result', JSON.stringify({
      taskId: currentTask, taskTitle: t.desc, f1: checkResult.f1,
      precision: checkResult.precision, recall: checkResult.recall,
      tp: checkResult.tp, total: checkResult.gt.length,
      boxes: boxes, message: msg, time: Date.now(),
    }));
  }
  try { window.parent.location.href = '/home'; } catch(e) { window.top.location.href = '/home'; }
}
```

> 实现者注意：各文件的标注数据变量不同（`boxes`/`entities`/`segments`/`taskGroup`），用 `||` 链兼容。`checkResult` 字段名一致（f1/precision/recall/tp/gt）。读各文件实际变量名调整。

- [ ] **Step 3: 验证**——无 tsc（纯 html/js），用 Node 语法检查 JS 段或人工核对。

---

### Task 2: home 页 auto-send 识别疑问标记

**Files:**
- Modify: `web/app/(workspace)/home/[[...sessionId]]/page.tsx`

- [ ] **Step 1: 识别疑问**——auto-send 块（L715-768）读 `annotation_doubt`：

```tsx
const isDoubt = localStorage.getItem("annotation_doubt") === "1";
localStorage.removeItem("annotation_doubt");
```

发送时若 isDoubt，消息前加优先级前缀（Coach 优先回应）：

```tsx
const finalMsg = isDoubt ? `[学生有疑问，优先回应] ${pendingMsg}` : pendingMsg;
```

> 放在现有 `sendMessage(enriched)` / `sendMessage(pendingMsg)` 处。保持评分卡逻辑不变（疑问也可能带结果）。

- [ ] **Step 2: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

---

### Task 3: PERSONA 加"疑问优先"规则

**Files:**
- Modify: `deeptutor/services/persona/presets/annotation-coach/PERSONA.md`（源文件）+ 同步运行时副本

- [ ] **Step 1: 加规则**——核心原则区加一条（学生标记疑问时优先回应）：

```markdown
14. **疑问优先** — 学生消息带"有疑问"标记/在消息开头标 ⚠ 时，**优先解答疑问**（先于流程推进、先于评测反馈）；解答清楚后再继续教学。进行中提问（未提交）视为最高优先级——先稳住学生、消除不确定，再谈下一步。
```

> 编号接现有最后一条（读 PERSONA 确认当前最大编号，用 14 或实际+1）。

- [ ] **Step 2: 同步运行时副本**——`data/user/workspace/personas/annotation-coach/PERSONA.md`（gitignored，但改动后需同步以便热加载）。

---

## 验证
- 前端：`cd web && npx tsc --noEmit`（清代理）
- 冒烟（可选，需服务）：标注台点"这里有疑问" → 跳 home → Coach 优先回应疑问
- 后端：PERSONA 改动无测试（仅文档），确认源+副本一致

## 提交（仅 commit，不 push）
- 按 Task 拆 2-3 个 commit：html 按钮 / home 识别 / PERSONA。
- **注意：触碰 `web/public/annotation_tool*.html` 是 O8 明确要求（此前"不触碰"约束仅指无关改动）。若 3modal 会话正在改这些文件，先确认无冲突（git status 检查）再改。**
