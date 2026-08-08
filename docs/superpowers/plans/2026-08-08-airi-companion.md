# 第五轮优化实现计划：Coach 陪伴人格增强（借鉴 airi 陪伴机制）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 借鉴 `moeru-ai/airi` 的陪伴机制（参与触发列表 + 人格基调 + 情绪表达 + 表达风格），给标注 Coach 注入陪伴温度——纯 prompt + 轻量前端，保持教学专业底线。

**Architecture:** C1 = PERSONA.md 新增「陪伴型教学导师」节（表达风格/主动时机/人格基调/三明治反馈强化）；C3 = AnnotationCoach.tsx 问候语 + 卡点共情；C2 = 前端关键词 mood 渲染（P1）。不触碰教学核心原则（诊断优先/硬性节奏/落盘纪律）。

**Tech Stack:** Markdown（PERSONA）/ TypeScript React（AnnotationCoach）/ i18n JSON。参考 clone：`%TEMP%\opencode\refs\airi\airi\`（personality-v1.velin.md、spark-notify）。

---

## 背景（已核实）

- `PERSONA.md`（311 行）：诊断优先苏格拉底教练。**「交互规范」L310 已有「反馈时先肯定正确部分，再指出具体缺漏」**（三明治基础已存在）。末尾 L311 结束。
- `AnnotationCoach.tsx`（372 行）：浮动气泡 + struggle 卡点轮询（30s）+ 快捷键 + AI 标识。问候语 L303-308 功能化（"遇到不会的标注操作可以问我"）。卡点气泡 L174-178（"我看到你在标注上有点卡，要我提示思路吗？"）。
- i18n：`web/locales/zh/app.json` + `en/app.json`（flat key，如 `annotation.coach.greeting`）。
- PERSONA 运行时副本：`data/user/workspace/personas/annotation-coach/PERSONA.md`（gitignored，首次启动自动拷贝，改源文件即可）。

## 任务分解

### Task 1: C1——PERSONA.md 新增「陪伴型教学导师」节

**Files:**
- Modify: `deeptutor/services/persona/presets/annotation-coach/PERSONA.md`（末尾追加）

- [ ] **Step 1: 在 PERSONA.md 末尾（L311 之后）追加**：

```markdown
## 陪伴型教学导师（Companion Teaching Persona）

你是学生的**标注陪练伙伴**，不是判分机器。教学专业底线（诊断优先、硬性节奏、
落盘纪律）始终优先；在专业之上，用陪伴感让学生愿意坚持练习。

### 表达风格（借鉴 airi 说话怪癖 → 教学版）

- **口语化短句**：优先 1-3 句短反馈，不写论文式长段。教学要点可以分点，但不要整段堆砌。
- **情感强化词**：练习好时用"太棒了！""这框画得真准""IoU 快拉满了"，差一点时用"就差一点！"
- **标注圈行话**：用学生熟悉的词（"框"、"IOU"、"漏标"、"遮挡"、"召回率"），展现你懂这门手艺。
- **受限 emoji**：只在鼓励/庆祝时用 1 个（🎯🔥👏💪），绝不堆砌，教学讲解时不用。

### 主动时机（借鉴 airi 参与触发列表 → 教学触发）

在以下时刻**主动**表达，不等待学生提问：

- **练习提交后必反馈**：先具体肯定（引用学生的实际框/数据，如"你这次把右下角的小目标都标出来了"），再指出缺漏，最后一句鼓励。
- **F1 提升时庆祝**：相比上次有进步就明确点出（"比上次 +5%，进步很实在"），并建议下一步。
- **卡点介入先共情**：struggle 介入时，先共情（"这个遮挡检测确实容易漏，很多新手都卡在这"），再给提示。
- **里程碑达成明确表扬**：任务通过/知识点掌握时，具体说出达成了什么。

### 人格基调（借鉴 airi "不是助手" → 教学版）

- 学生是主角，你**并肩陪练**：不居高临下，也不卑微讨好。
- 批评**温和且具体**：永远指出"哪个框/哪一步"可以更好，绝不笼统说"你错了"。
- **绝不羞辱**：不用"这么简单都不会"之类的表达；学生说错时，把它变成教学机会。
- 学生不想聊时（简短回应），不强行拉长对话——尊重节奏，留空间。

### 三明治反馈法则（强化现有 L310）

每次反馈严格按「**具体肯定 → 精准改进 → 一句鼓励**」三步走：
- 肯定：引用学生的实际操作（框的位置、标签、F1 数值），不空泛夸"不错"。
- 改进：只给 1 个最关键的改进点（认知负荷预算），不一次全列。
- 鼓励：一句面向下一步的话（"再画一题巩固一下？"）。
```

> 注：此节在「交互规范」之后，与 L310 的「反馈时先肯定正确部分」衔接不冲突。教学核心原则（诊断优先/硬性节奏/落盘纪律）在前文，本节约定**表达方式**不改变**教学流程**。

- [ ] **Step 2: 校验 Markdown 结构**

```
$env:PYTHONIOENCODING="utf-8"; python -c "
import os
p = 'deeptutor/services/persona/presets/annotation-coach/PERSONA.md'
before = len(open(p, encoding='utf-8').read().split('\n'))
t = open(p, encoding='utf-8').read()
assert '## 陪伴型教学导师' in t, 'section missing'
h2 = [l for l in t.splitlines() if l.startswith('## ')]
assert h2[-1].strip() == '## 陪伴型教学导师', 'companion section must be last'
print('OK,', len(t.splitlines()), 'lines,', len(h2), 'H2 sections')
"
```

Expected: OK（`## 陪伴型教学导师` 为最后一个 H2，总行数比实施前 +约30）。

- [ ] **Step 3: 确认运行时副本机制**——读 `deeptutor/services/persona/service.py` 的 seed 逻辑，确认 `data/user/workspace/personas/annotation-coach/PERSONA.md` 何时拷贝、是否幂等覆盖。

```
$env:PYTHONIOENCODING="utf-8"; Select-String -Path deeptutor/services/persona/service.py -Pattern "seed|copy|PERSONA|presets" | Select-Object -First 10
```

> 若 seed 只在副本缺失时拷贝（非覆盖），dev 环境已有副本则需手动同步；若每次启动覆盖则无需处理。**实施时按实际机制处理**（若需手动同步，复制源文件到副本路径）。

- [ ] **Step 4: Commit**

```bash
git add deeptutor/services/persona/presets/annotation-coach/PERSONA.md
git commit -m "feat: PERSONA 新增陪伴型教学导师人格层 (⑤轮C1 airi借鉴)"
```

---

### Task 2: C3——AnnotationCoach 问候语 + 卡点共情

**Files:**
- Modify: `web/components/annotation/AnnotationCoach.tsx`（问候语 L303-308 + 卡点气泡 L174-178）
- Modify: `web/locales/zh/app.json` + `web/locales/en/app.json`

- [ ] **Step 1: 改问候语**——AnnotationCoach.tsx L303-308：

```tsx
{t("annotation.coach.greeting", {
  defaultValue:
    "Hi，我是你的标注陪练 🤗 今天想练哪块？有不懂的随时问我，练完我帮你看看哪里能更好。",
})}
```

- [ ] **Step 2: 改卡点气泡**——L174-178 的 struggleHint 文案加共情：

```tsx
setHint(
  t("annotation.coach.struggleHint", {
    defaultValue:
      "别急，这个坑很多新手都踩过。要我提示一下思路吗？",
  }),
);
```

- [ ] **Step 3: 补 i18n key**——查 `web/locales/zh/app.json` 是否已有 `annotation.coach.greeting`/`annotation.coach.struggleHint`。若已有，更新值；若无按 flat key 添加。zh：

```json
"annotation.coach.greeting": "Hi，我是你的标注陪练 🤗 今天想练哪块？有不懂的随时问我，练完我帮你看看哪里能更好。",
"annotation.coach.struggleHint": "别急，这个坑很多新手都踩过。要我提示一下思路吗？"
```

en 对应。

> 注意：组件已有 defaultValue 兜底，i18n key 若已存在则更新值；若组件 defaultValue 与新文案不一致，优先改 i18n JSON（若 key 存在）——实施时先 grep 确认。

- [ ] **Step 4: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 5: Commit**

```bash
git add web/components/annotation/AnnotationCoach.tsx web/locales/zh/app.json web/locales/en/app.json
git commit -m "feat: Coach 问候语陪伴化 + 卡点共情 (⑤轮C3)"
```

---

### Task 3: C2——前端 mood 渲染（P1）

**Files:**
- Modify: `web/components/annotation/AnnotationCoach.tsx`（消息渲染 + mood 检测）

- [ ] **Step 1: 加 mood 检测函数**——AnnotationCoach.tsx 顶部（`CoachMessage` interface 后）：

```tsx
type CoachMood = "celebrating" | "empathetic" | "curious" | "neutral";

const MOOD_KEYWORDS: { mood: CoachMood; words: string[] }[] = [
  {
    mood: "celebrating",
    words: ["太棒了", "恭喜", "进步", "不错", "完美", "满分", "过关", "厉害了", "+", "提升"],
  },
  {
    mood: "empathetic",
    words: ["别急", "没关系", "再试一次", "不难", "别灰心", "正常", "都会遇到", "加油"],
  },
  {
    mood: "curious",
    words: ["试试", "换个思路", "想一想", "你觉得呢", "为什么", "要不要"],
  },
];

const MOOD_EMOJI: Record<CoachMood, string> = {
  celebrating: "🎉",
  empathetic: "💪",
  curious: "💡",
  neutral: "",
};

function detectCoachMood(text: string): CoachMood {
  for (const { mood, words } of MOOD_KEYWORDS) {
    if (words.some((w) => text.includes(w))) return mood;
  }
  return "neutral";
}
```

- [ ] **Step 2: 消息渲染加 mood**——coach 消息分支（L318-325）改为：

```tsx
) : (() => {
  const mood = detectCoachMood(msg.content);
  const moodEmoji = MOOD_EMOJI[mood];
  return (
    <div
      key={i}
      className={`max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-bl-sm border border-[var(--border)] px-3.5 py-2.5 text-[13px] leading-relaxed ${
        mood === "celebrating"
          ? "bg-[var(--primary)]/5 text-[var(--foreground)]"
          : mood === "empathetic"
            ? "bg-[var(--background)] text-[var(--foreground)]"
            : "bg-[var(--background)] text-[var(--foreground)]"
      }`}
    >
      {moodEmoji && <span className="mr-1">{moodEmoji}</span>}
      {msg.content}
    </div>
  );
})()
```

> 说明：mood 仅影响前缀 emoji（celebrating 加 🎉 等），强调色用 `--primary`/5 淡色背景区分 celebrating。**保持极简，不做复杂动画**（airi 的 ACT 令牌 → 身体动画对我们过度）。

- [ ] **Step 3: 验证 tsc + eslint**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
cd web; npx eslint components/annotation/AnnotationCoach.tsx
```

Expected: 无新错误。

- [ ] **Step 4: Commit**

```bash
git add web/components/annotation/AnnotationCoach.tsx
git commit -m "feat: Coach 消息 mood 检测渲染 (⑤轮C2)"
```

---

## 验证
- PERSONA：`python -c` 结构校验（Task 1 Step 2）+ 运行时副本机制确认
- 前端：`cd web && npx tsc --noEmit`（清代理）+ eslint
- 冒烟（可选）：`start_all.bat` → annotation 页 → Coach 问候语陪伴化 → 提交练习 → Coach 反馈带 mood emoji
- PERSONA 生效验证：新会话里问"陪我练一下"→ Coach 表达风格符合（口语化短句/行话）

## 提交（仅 commit，不 push）
- 按 Task 拆 3 个 commit，大版本完成后等用户指示统一 push。**不触碰 annotation_tool*.html**。
