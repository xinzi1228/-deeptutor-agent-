# 「标注星图」工作台彻底改造实施计划（Workbench Restructure）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 DeepTutor fork 彻底改造为「标注星图」数据标注教学 Agent 产品——删除 9 个通用路由目录、侧边栏裁 4 项、保留页面 UI 入口裁剪、品牌替换、后端只留 chat capability 与 annotation-coach persona。

**Architecture:** 前端删除路由目录（页面不可达）+ `SidebarShell` 导航裁剪 + 保留页面（Home/Memory）内 UI 入口裁剪；被保留页面依赖的共享组件代码保留。后端 `builtin_capabilities.py` 只留 chat，`persona/presets` 只留 annotation-coach。品牌 i18n 批量替换（保留 key）。

**Tech Stack:** Next.js (App Router, TSX), react-i18next (扁平 JSON), Python 3.13, pytest。前端验证用 `tsc --noEmit` + `npm run build`；后端用 pytest 回归。**前端裁剪任务无单元测试逻辑，验证靠 tsc + 构建 + 手动冒烟。**

**Spec:** `docs/specs/workbench-restructure-design.md`（已提交 `877237a3`，含 3.1a 裁剪粒度决策）

---

### Task 1: 后端 capability 白名单——只保留 chat

**Files:**
- Modify: `deeptutor/runtime/bootstrap/builtin_capabilities.py`
- Test: `tests/runtime/test_builtin_capabilities.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/runtime/test_builtin_capabilities.py`:

```python
"""Builtin capability whitelist — only chat remains (标注星图 teaching product)."""

from __future__ import annotations


def test_only_chat_capability_registered() -> None:
    from deeptutor.runtime.bootstrap.builtin_capabilities import BUILTIN_CAPABILITY_CLASSES

    assert set(BUILTIN_CAPABILITY_CLASSES.keys()) == {"chat"}


def test_chat_capability_class_resolvable() -> None:
    from deeptutor.runtime.bootstrap.builtin_capabilities import BUILTIN_CAPABILITY_CLASSES

    cls = BUILTIN_CAPABILITY_CLASSES["chat"]
    module_path, _, attr = cls.partition(":")
    import importlib

    mod = importlib.import_module(module_path)
    assert hasattr(mod, attr)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/runtime/test_builtin_capabilities.py -v`
Expected: FAIL — `set(BUILTIN_CAPABILITY_CLASSES.keys())` contains 7 items, not `{"chat"}`

- [ ] **Step 3: Edit the registry**

Replace the contents of `deeptutor/runtime/bootstrap/builtin_capabilities.py`:

```python
"""Built-in capability class paths (标注星图 teaching product — only chat)."""

BUILTIN_CAPABILITY_CLASSES: dict[str, str] = {
    "chat": "deeptutor.agents.chat.capability:ChatCapability",
}
```

- [ ] **Step 4: Check for downstream references to removed capabilities**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -c "import re,pathlib; [print(f) for f in ['deeptutor_cli/main.py'] if pathlib.Path(f).exists()]"`

Then grep the repo for references to removed capability names (excluding docs/specs and the capability implementation dirs themselves):
Run: `grep -rn "deep_solve\|deep_question\|deep_research\|math_animator\|\"visualize\"\|mastery_path" deeptutor deeptutor_cli tests -l 2>&1 | Select-String -NotMatch "capabilities|agents|builtin_capabilities"`

Review each hit. Likely findings:
- `deeptutor_cli/main.py:80` — just a help-string example listing capability names; update it to only mention `chat` (optional, cosmetic).
- Capability implementation files (they stay on disk but unused).
- Tests that may import removed capabilities — if a test depends on a removed capability being registered, adjust the test to not rely on it (note what you changed in your report).

Fix any **functional** reference that would break at import/runtime (not the implementation files themselves, which stay).

- [ ] **Step 5: Run tests to verify it passes**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/runtime/test_builtin_capabilities.py -v`
Expected: PASS (2 passed)

Run broader regression: `python -m pytest tests/core tests/runtime tests/cli -q 2>&1 | Select-Object -Last 5`
If failures appear that are clearly caused by the capability removal (not pre-existing), fix the test or the reference and note it. If failures are pre-existing/unrelated, note and continue.

- [ ] **Step 6: Commit**

```bash
git add deeptutor/runtime/bootstrap/builtin_capabilities.py tests/runtime/test_builtin_capabilities.py deeptutor_cli/main.py
git commit -m "feat: capability 白名单只留 chat (标注星图产品定位)"
```

---

### Task 2: 后端 persona 白名单——只留 annotation-coach

**Files:**
- Modify: `deeptutor/services/persona/service.py` (LEGACY_PERSONA_SKILLS)
- Delete: `deeptutor/services/persona/presets/peer/`, `presets/research-assistant/`, `presets/teacher/`
- Test: `tests/services/test_persona_whitelist.py` (create)

- [ ] **Step 1: Read current persona service**

Read `deeptutor/services/persona/service.py` — focus on how presets are discovered, the `LEGACY_PERSONA_SKILLS` tuple (line ~52), and how the default persona is chosen. Also list `deeptutor/services/persona/presets/` to confirm the 4 preset dirs.

- [ ] **Step 2: Write the failing test**

Create `tests/services/test_persona_whitelist.py`:

```python
"""Persona whitelist — only annotation-coach remains (标注星图 teaching product)."""

from __future__ import annotations

from pathlib import Path


def test_only_annotation_coach_preset_remains() -> None:
    presets_dir = Path(__file__).resolve().parents[2] / "deeptutor/services/persona/presets"
    dirs = {p.name for p in presets_dir.iterdir() if p.is_dir()}
    assert dirs == {"annotation-coach"}


def test_default_persona_is_annotation_coach() -> None:
    from deeptutor.services.persona.service import DEFAULT_PERSONA

    assert DEFAULT_PERSONA == "annotation-coach"
```

Before writing, read `service.py` to find the actual default persona constant/name. If the default is not a module-level constant named `DEFAULT_PERSONA`, name the test to match the real symbol (e.g. import the service and check its default resolution returns `annotation-coach`). Adjust the test accordingly — the **requirement** is: the default persona resolves to `annotation-coach`.

- [ ] **Step 3: Run test to verify it fails**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/services/test_persona_whitelist.py -v`
Expected: FAIL — 4 preset dirs exist, or default is not annotation-coach

- [ ] **Step 4: Implement**

1. Delete the 3 preset directories:
```bash
Remove-Item -Recurse -Force "D:\自己\git帅\-deeptutor-agent-\deeptutor\services\persona\presets\peer", "D:\自己\git帅\-deeptutor-agent-\deeptutor\services\persona\presets\research-assistant", "D:\自己\git帅\-deeptutor-agent-\deeptutor\services\persona\presets\teacher"
```

2. Update `LEGACY_PERSONA_SKILLS` in `service.py` — if it references removed personas, either empty it or keep only entries that still resolve. Read the surrounding code to decide: this tuple maps legacy persona names to skills for migration. If the mapped skills still exist as skills, keep the mapping (it's harmless); if it breaks on a missing preset, guard it. Prefer minimal change: if the tuple is only used to detect/convert legacy persona selections and the personas no longer exist, simplify it to only reference `annotation-coach` or an empty tuple — but ONLY if that doesn't break migration logic. Note your decision in the report.

3. If the service has a persona list endpoint that enumerates presets dynamically (reads the presets dir), no further change is needed — deletion is enough. If there's a hardcoded list of persona names elsewhere in the backend, remove non-annotation-coach entries.

- [ ] **Step 5: Verify annotation-coach workspace runtime copy is untouched**

Check the runtime workspace persona copy still exists (it contains struggle_detect rule 12):
Run: `Test-Path "D:\自己\git帅\-deeptutor-agent-\data\user\workspace\personas\annotation-coach\PERSONA.md"` → expect `True`. If missing, note it (do NOT recreate from scratch unless needed).

- [ ] **Step 6: Run tests + regression**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/services/test_persona_whitelist.py -v`
Expected: PASS

Run regression: `python -m pytest tests/services/test_persona.py tests/services/test_learning_records.py tests/services/test_skill_service.py -q 2>&1 | Select-Object -Last 5` (adjust test file names to whatever persona-related tests exist — grep `tests/` for persona tests first). Fix only breakage caused by this change.

- [ ] **Step 7: Commit**

```bash
git add deeptutor/services/persona/service.py tests/services/test_persona_whitelist.py
git commit -m "feat: persona 白名单只留 annotation-coach + 固定默认 (标注星图)"
```
(Git will record the preset deletions automatically via `git add -A` on the presets path; if deletions aren't staged, run `git add -A deeptutor/services/persona/presets/` too.)

---

### Task 3: 删除 9 个通用前端路由目录

**Files:**
- Delete: `web/app/(workspace)/book/`, `co-writer/`, `partners/`, `playground/`
- Delete: `web/app/(utility)/agents/`, `knowledge/`, `notebook/`, `space/`, `profile/`

- [ ] **Step 1: Pre-check references to deleted page dirs**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit 2>&1 | Select-Object -First 5`
Record the current baseline (expect 0 errors before deletion).

Then grep for imports that target deleted route dirs (these would break tsc after deletion). Likely culprits are components importing from removed pages — but Next.js pages are usually self-contained. The risk is `components/*` that import libs still present (safe). Run:
`grep -rn "@/\?app/(workspace)/\(book\|co-writer\|partners\|playground\)" web/components web/app web/lib --include="*.tsx" --include="*.ts" | Select-Object -First 30`

If any file under a **retained** route imports a file under a **deleted** route, note it — Task 5 handles the retained-page UI cleanup, but a hard import of a deleted page module must be removed here.

- [ ] **Step 2: Delete the route directories**

```bash
Remove-Item -Recurse -Force "D:\自己\git帅\-deeptutor-agent-\web\app\(workspace)\book", "D:\自己\git帅\-deeptutor-agent-\web\app\(workspace)\co-writer", "D:\自己\git帅\-deeptutor-agent-\web\app\(workspace)\partners", "D:\自己\git帅\-deeptutor-agent-\web\app\(workspace)\playground", "D:\自己\git帅\-deeptutor-agent-\web\app\(utility)\agents", "D:\自己\git帅\-deeptutor-agent-\web\app\(utility)\knowledge", "D:\自己\git帅\-deeptutor-agent-\web\app\(utility)\notebook", "D:\自己\git帅\-deeptutor-agent-\web\app\(utility)\space", "D:\自己\git帅\-deeptutor-agent-\web\app\(utility)\profile"
```

- [ ] **Step 3: Run tsc to find breakage**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit 2>&1 | Select-Object -First 60`

Every error is an import of a deleted page/route module from retained code. Fix each by removing the offending import/render. Most will be in components that are ONLY used by deleted pages (then remove the component usage in retained pages), or `lib/*` modules that still exist (then the import is fine and the error is elsewhere).

Expected error categories:
- `Cannot find module '@/app/...'` or a page component — remove the import.
- References to deleted route strings like `/co-writer`, `/book`, `/space/...`, `/partners` in retained pages (`MemorySection`, `SessionActivityPanel`) — these are **runtime link strings, not imports**, so tsc won't catch them; Task 5 removes them.

Fix only the **import/module resolution errors** here. Runtime-link cleanup is Task 5.

- [ ] **Step 4: Verify tsc clean**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit 2>&1 | Select-Object -Last 5`
Expected: no output (0 errors)

- [ ] **Step 5: Commit**

```bash
git add -A web/app
git commit -m "feat: 删除 9 个通用前端路由目录 (book/co-writer/partners/playground/agents/knowledge/notebook/space/profile)"
```
(Stage all deletions; also stage any import fixes made in Step 3.)

---

### Task 4: 侧边栏导航裁剪（SidebarShell）

**Files:**
- Modify: `web/components/sidebar/SidebarShell.tsx`

- [ ] **Step 1: Edit PRIMARY_NAV**

In `web/components/sidebar/SidebarShell.tsx`, replace the `PRIMARY_NAV` array (currently lines 45-102) with only:

```tsx
const PRIMARY_NAV: NavEntry[] = [
  {
    href: "/home",
    label: "Home",
    icon: House,
    tooltipKey: "Home tooltip",
    requires: "llm",
  },
  {
    href: "/annotation",
    label: "Annotation",
    icon: Tag,
    tooltipKey: "Annotation tooltip",
  },
  {
    href: "/progress",
    label: "Progress",
    icon: TrendingUp,
    tooltipKey: "Progress tooltip",
  },
];
```

- [ ] **Step 2: Edit SECONDARY_NAV**

Replace the `SECONDARY_NAV` array (currently lines 104-124) with only:

```tsx
const SECONDARY_NAV: NavEntry[] = [
  { href: "/memory", label: "Memory", icon: Brain, tooltipKey: "Memory tooltip" },
  { href: "/settings", label: "Settings", icon: Settings },
];
```

- [ ] **Step 3: Remove now-unused icon imports**

After the nav edits, remove unused imports from the `lucide-react` import block (lines 8-27): `HeartHandshake`, `Bot`, `LayoutGrid`, `Library`, `PenLine`, `BookOpen` — only if they are no longer referenced anywhere in the file (grep the file for each). Keep `House`, `Tag`, `TrendingUp`, `Brain`, `Settings`, and any still used.

- [ ] **Step 4: Verify tsc**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit 2>&1 | Select-Object -Last 5`
Expected: no output

- [ ] **Step 5: Commit**

```bash
git add web/components/sidebar/SidebarShell.tsx
git commit -m "feat: 侧边栏导航裁 4 项 (Home/Annotation/Progress + Memory/Settings)"
```

---

### Task 5: 保留页面 UI 入口裁剪（Memory / Home）

**Files:**
- Modify: `web/components/memory/MemorySection.tsx`
- Modify: `web/components/chat/home/SessionActivityPanel.tsx`
- Modify: `web/components/chat/home/ChatComposer.tsx`
- Possibly: `web/components/chat/home/ChatMessages.tsx`, `web/components/chat/space/ChatSpaceMenu.tsx` (if Composer edit cascades)

This is the most delicate task. Work incrementally, running `tsc` after each file.

- [ ] **Step 1: MemorySection — remove removed-entity jump branches**

In `web/components/memory/MemorySection.tsx`, around lines 220-250 there is a switch that maps entity kinds to routes (`/co-writer/...`, `/space/notebooks`, `/book?...`, `/partners/...`, `/space/questions`, `/knowledge?...`). Replace the branches for removed routes with a fallback that opens the session (`/home/<id>`) or removes the link. Keep the `/home/...` branch (line 223).

Read the function first; the exact structure determines the edit. Requirement: **no retained page may produce a link to a deleted route**. Note in your report which branches you changed.

- [ ] **Step 2: SessionActivityPanel — remove space links**

In `web/components/chat/home/SessionActivityPanel.tsx`, the activity entries map to `/space/chat-history`, `/space/books`, `/space/notebooks`, `/space/questions`, `/space/personas` (lines ~153-177). Remove or re-point those entries. Keep any that resolve within retained pages (e.g. `/home`, `/memory`, `/progress`).

- [ ] **Step 3: ChatComposer — remove context selectors for removed features**

In `web/components/chat/home/ChatComposer.tsx` (1061 lines), the composer has a context-chooser area (`ChatSpaceMenu`) that surfaces book/space/notebook/agents/question-bank attachments, plus `AgentSelector`/`KnowledgeSelector`/`PersonaSelector`/`ModelSelector`.

Requirement: **remove the UI entry points for removed features** — book / space / notebook / agents / question-bank / partners. Keep model and persona selectors (model is required to pick an LLM; persona will be fixed to annotation-coach in a later pass, so the selector can stay for now or be hidden — your call, but do not break the composer).

Concretely:
1. Remove `ChatSpaceMenu` usage and the space-selection state (`SpaceSelectionCounts`, `SelectedBookReference`, `SpaceMemoryFile`, book/notebook/question-bank picker types) that is only used to feed the removed menu. If removing the whole state graph is risky, **minimal alternative**: keep the types/state but do not render `ChatSpaceMenu` (comment out the JSX with a note). The safe minimal edit is: don't render `ChatSpaceMenu` + remove its import if unused.
2. Remove `AgentSelector` if it only connects to `/partners` / My Agents; keep `ModelSelector` and `PersonaSelector`.
3. Run `npx tsc --noEmit` and fix fallout (unused imports, unused vars — remove them).

PREFER minimal, safe edits over a large rewrite. The goal is: the composer's UI no longer offers book/space/notebook/agents/question-bank context, but the composer still composes and sends messages correctly.

- [ ] **Step 4: Verify tsc clean**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit 2>&1 | Select-Object -Last 5`
Expected: no output

- [ ] **Step 5: Verify no dead links to removed routes remain in retained pages**

Run: `grep -rn "co-writer\|/partners\|/playground\|/space/\|/agents\|/knowledge\|/notebook\|/profile\|/book" web/app web/components/memory web/components/chat/home --include="*.tsx" | Select-String -NotMatch "components/(agents|knowledge|space|book|partners|notebook|quiz|research|visualize|playground)/" | Select-Object -First 30`

Review each hit — it should be in a deleted-route's own component (fine) or in code you can justify keeping (e.g. an API lib import). Any hit in a **retained page's UI** that links to a deleted route must be handled.

- [ ] **Step 6: Commit**

```bash
git add web/components/memory/MemorySection.tsx web/components/chat/home/SessionActivityPanel.tsx web/components/chat/home/ChatComposer.tsx web/components/chat/home/ChatMessages.tsx
git commit -m "feat: 保留页面 UI 入口裁剪 (Memory/Home 移除已删功能入口)"
```
(Stage exactly the files you changed.)

---

### Task 6: 品牌替换——「标注星图」

**Files:**
- Modify: `web/locales/zh/app.json`, `web/locales/en/app.json`
- Modify: `web/app/layout.tsx`
- Modify: `web/app/(auth)/login/page.tsx`, `web/app/(auth)/register/page.tsx`
- Modify: `web/app/(admin)/admin/users/page.tsx`
- Modify: `web/components/sidebar/SidebarShell.tsx` (banner/logo alt if branded)
- Modify: `web/components/sidebar/VersionBadge.tsx` (if it shows "DeepTutor")

- [ ] **Step 1: Back up the locale files**

```bash
Copy-Item "D:\自己\git帅\-deeptutor-agent-\web\locales\zh\app.json" "C:\Users\free\AppData\Local\Temp\opencode\app.zh.backup.json"
Copy-Item "D:\自己\git帅\-deeptutor-agent-\web\locales\en\app.json" "C:\Users\free\AppData\Local\Temp\opencode\app.en.backup.json"
```

- [ ] **Step 2: Batch-replace values in locale JSON (keep keys)**

Run a Python script that loads each JSON, and for every **value** string replaces "DeepTutor" with the product name — zh → "标注星图", en → "Annotation Star Map" — then writes back preserving structure:

```powershell
cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -c @"
import json, io
from pathlib import Path

def replace_vals(obj, f):
    if isinstance(obj, dict):
        return {k: replace_vals(v, f) for k, v in obj.items()}
    if isinstance(obj, list):
        return [replace_vals(v, f) for v in obj]
    if isinstance(obj, str):
        return f(obj)
    return obj

for path, name in [("web/locales/zh/app.json", "标注星图"), ("web/locales/en/app.json", "Annotation Star Map")]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    data = replace_vals(data, lambda s: s.replace("DeepTutor", name))
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("replaced", path)
"@
```

- [ ] **Step 3: Verify replacement coverage**

Run: `grep -c "DeepTutor" "D:\自己\git帅\-deeptutor-agent-\web\locales\zh\app.json"` and same for en.
Expected: 0 (all values replaced; keys are English originals and should NOT contain "DeepTutor" — if a key contains DeepTutor, leave it, since keys are identifiers).

- [ ] **Step 4: Update non-locale brand locations**

- `web/app/layout.tsx` line 24: `title: "DeepTutor"` → `title: "标注星图"`
- `web/app/(admin)/admin/users/page.tsx` line 469: the `t("DeepTutor Admin · User Management")` key's **value** was already replaced in Step 2; no code change needed unless the key itself is rendered raw — check and note.
- `web/app/(auth)/login/page.tsx` and `register/page.tsx`: replace any hardcoded "DeepTutor" strings (welcome text, brand mark) with 标注星图. Grep both files for "DeepTutor".
- `web/components/sidebar/SidebarShell.tsx`: logo/banner alt text — check for "DeepTutor" brand strings; the `Image` alts point to `/logo.png` / `/banner.png` assets (keep the files). If alt text says DeepTutor, update to 标注星图.
- `web/components/sidebar/VersionBadge.tsx`: if it renders "DeepTutor", update.

- [ ] **Step 5: Final residual grep (code, not locales)**

Run: `grep -rn "DeepTutor" web/components web/app web/lib --include="*.tsx" --include="*.ts" | Select-String -NotMatch "locales|deeptutor.info|GITHUB_REPO_URL|github.com" | Select-Object -First 40`

Review each residual: acceptable residuals are technical identifiers, URLs, or comments. Any user-facing brand string must be replaced.

- [ ] **Step 6: Verify tsc**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit 2>&1 | Select-Object -Last 5`
Expected: no output

- [ ] **Step 7: Commit**

```bash
git add web/locales/zh/app.json web/locales/en/app.json web/app/layout.tsx web/app/'(auth)' web/app/'(admin)' web/components/sidebar
git commit -m "feat: 品牌替换为「标注星图」 (i18n 值批量替换 + layout/登录页/admin/侧边栏)"
```

---

### Task 7: 全量验证 + 冒烟

**Files:** none (verification only)

- [ ] **Step 1: Backend full test regression**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/ -q 2>&1 | Select-Object -Last 8`
Expected: no new failures vs pre-change baseline. Note any pre-existing failures (e.g. `test_file_tools.py` Windows path-separator failure is known pre-existing — confirm it's the same failure, not a new one).

- [ ] **Step 2: Frontend tsc + build**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit 2>&1 | Select-Object -Last 5` → expected no output.
Then: `npm run build 2>&1 | Select-Object -Last 25` → expected success (Next.js build completes). If build fails on a runtime error (e.g. server component importing a deleted module), fix it and note.

- [ ] **Step 3: Manual smoke via playwright (or instruct user)**

Start backend + frontend (separate terminals):
```powershell
# terminal 1
cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m deeptutor_cli.main serve --port 8001
# terminal 2
cd "D:\自己\git帅\-deeptutor-agent-\web"; npx next dev --port 3782
```

Use playwright (or ask the user to click through) to verify:
1. Load `http://localhost:3782/login` → brand shows 标注星图
2. Log in → lands on `/home` (root redirect)
3. Sidebar shows only Home / Annotation / Progress / Memory / Settings
4. Visiting `/book`, `/partners`, `/space`, `/knowledge` → 404 or redirect, not a broken page
5. `/annotation` loads (Label Studio embed or annotation UI)
6. `/progress` loads (learning report)
7. Home composer: no book/space/notebook/agents chooser visible; can type and send a message

If playwright is not available, record these as manual steps for the user and mark smoke as "needs manual verification".

- [ ] **Step 4: Commit any smoke fixes**

If smoke found issues, fix and commit them with a descriptive message. Otherwise no commit.

---

### Task 8: 文档同步

**Files:**
- Modify: `README.md` (project root — update product name/description to 标注星图 if it describes the product)
- Modify: `docs/session-handoff.md` (update product name + completed workbench restructure)
- Modify: `docs/fork-features.md` (add 工作台彻底改造 to the feature list)

- [ ] **Step 1: Read the current docs**

Read `README.md`, `docs/session-handoff.md`, `docs/fork-features.md` — identify where the product is named "DeepTutor" or where the workbench feature list needs a new entry.

- [ ] **Step 2: Update README**

Update the product description to reflect 标注星图 (data annotation teaching agent product). Keep technical instructions intact. Do not over-edit — change only the product-name/positioning lines.

- [ ] **Step 3: Update handoff + fork-features**

- `docs/session-handoff.md`: mark workbench restructure as completed (add to 已完成功能), update product name, update the 专门化改造 todo (only 任务引导引擎化 remains).
- `docs/fork-features.md`: add a section describing the 工作台彻底改造 (route pruning, nav pruning, brand, capability/persona whitelist).

- [ ] **Step 4: Commit**

```bash
git add -f README.md docs/session-handoff.md docs/fork-features.md
git commit -m "docs: 同步标注星图品牌 + 工作台彻底改造功能清单"
```
(docs/ and README may be gitignored — use `-f`; check `git status` first.)

---

## Self-Review

**1. Spec coverage:**
- §3.1 路由移除 → Task 3
- §3.1a 保留页面 UI 入口裁剪 → Task 5
- §3.2 侧边栏导航 → Task 4
- §3.3 默认路由 → 已现成（`(workspace)/page.tsx` 根重定向 `/home` + login `next` 默认 `/`），Task 3/7 冒烟验证，无需新代码
- §3.4 品牌 → Task 6
- §4.1 capability 白名单 → Task 1
- §4.2 persona 白名单 → Task 2
- §4.3 工具全保留 → 无任务（不改注册）
- §6 验证 → Task 7
- 文档同步 → Task 8
✅ 全覆盖

**2. Placeholder scan:** 所有代码块完整。Task 2 的 `DEFAULT_PERSONA` 符号名需实现者按实际读取调整（明确标注了）；Task 5 是最小安全编辑原则（给出编辑指令 + 验证步骤，因 ChatComposer 1061 行无法逐行预写）。

**3. Type consistency:**
- capability 白名单: `BUILTIN_CAPABILITY_CLASSES` dict 只留 `chat` → Task 1/7 一致
- persona: `annotation-coach` 默认 + 唯一 preset → Task 2 一致
- 保留路由: `/home` `/annotation` `/progress` `/memory` `/settings` → Task 3/4/7 一致
- 品牌: zh「标注星图」en「Annotation Star Map」→ Task 6/8 一致

**已知风险：**
1. Task 3 删除路由后 tsc 报错需逐条修复——实现者需判断是 import 错误（修）还是运行时链接字符串（留到 Task 5）
2. Task 5 ChatComposer 最小编辑原则：宁可保留未用状态图（注释 JSX）也不要大改导致发送功能损坏——验证靠 tsc + 冒烟
3. 后端测试可能有依赖已移除 capability 的测试——Task 1 Step 5 处理
4. persona legacy 迁移逻辑（LEGACY_PERSONA_SKILLS）——Task 2 Step 4 需实现者按实际决策
