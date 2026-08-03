# 引用溯源实施计划（规范库页 + 对话自动检测）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增标注规范库页（文档+章节可查看）+ 对话内 `〔规范: 文档名§章节〕` 引用可点击弹窗看原文。

**Architecture:** 后端 `GET /api/v1/standards` 从 annotation-guide skill references 读文档+章节；前端侧边栏「标注规范」页渲染文档；RichMarkdownRenderer 增强识别 `〔规范: ...〕` 标记 → StandardDialog 弹窗。

**Tech Stack:** Python FastAPI, Next.js, react-markdown, react-i18next。

**Spec:** `docs/specs/standards-trace-design.md`（已提交 `cd0059da`）

---

### Task 1: 后端 `GET /api/v1/standards`

**Files:**
- Create: `deeptutor/api/routers/standards.py`
- Modify: `deeptutor/api/main.py`（挂载路由）
- Test: `tests/api/test_standards.py`

- [ ] **Step 1: 写失败测试**

```python
"""standards endpoint — annotation standards catalog from skill references."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_standards_returns_documents():
    from deeptutor.api.routers.standards import standards

    result = await standards()
    assert "standards" in result
    docs = result["standards"]
    assert len(docs) >= 4, "expected the annotation-guide reference docs"
    for d in docs:
        assert d["id"]
        assert d["title"]
        assert "sections" in d
        assert "content" in d


@pytest.mark.asyncio
async def test_standards_bbox_has_expected_section():
    from deeptutor.api.routers.standards import standards

    result = await standards()
    docs = {d["id"]: d for d in result["standards"]}
    assert "bbox-guide" in docs
    assert any("边界框" in s for s in docs["bbox-guide"]["sections"])
```

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_standards.py -v 2>&1 | Select-Object -Last 6`
Expected: FAIL (ImportError)

- [ ] **Step 2: 实现 standards.py**

Create `deeptutor/api/routers/standards.py`:

```python
"""Standards catalog — annotation standards from the annotation-guide skill."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter()

# annotation-guide skill references (source of truth for annotation standards)
_STANDARDS_DIR = (
    Path(__file__).resolve().parents[2] / "skills" / "builtin" / "annotation-guide" / "references"
)


def _extract_sections(text: str) -> list[str]:
    """Extract ## / ### heading texts (section titles)."""
    return [
        m.group(1).strip()
        for m in re.finditer(r"^#{2,3}\s+(.+)$", text, re.MULTILINE)
        if m.group(1).strip()
    ]


def _derive_title(md: Path, text: str) -> str:
    """First # heading, else readable filename."""
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return md.stem.replace("-", " ").title()


@router.get("/standards")
async def standards() -> dict[str, Any]:
    """标注规范文档目录（来自 annotation-guide skill references）。"""
    docs = []
    if _STANDARDS_DIR.exists():
        for md in sorted(_STANDARDS_DIR.glob("*.md")):
            try:
                text = md.read_text(encoding="utf-8")
            except OSError:
                continue
            docs.append({
                "id": md.stem,
                "title": _derive_title(md, text),
                "sections": _extract_sections(text),
                "content": text,
            })
    return {"standards": docs}
```

NOTE: verify the path `parents[2]` resolves correctly — `standards.py` is at `deeptutor/api/routers/`, so `parents[0]=routers, parents[1]=api, parents[2]=deeptutor`, then `/skills/builtin/annotation-guide/references`. Confirm the actual skill dir exists at that path (`deeptutor/skills/builtin/annotation-guide/references/`).

- [ ] **Step 3: 挂载到 main.py**

In `deeptutor/api/main.py`, find where other routers are included (e.g. `knowledge.router`), and add:

```python
from deeptutor.api.routers import standards as standards_router  # near other imports
...
app.include_router(
    standards_router.router,
    prefix="/api/v1",
    tags=["standards"],
    dependencies=_auth,
)
```

Follow the exact import + include pattern used for sibling routers (auth dependency `_auth`).

- [ ] **Step 4: 运行测试确认通过**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_standards.py -v 2>&1 | Select-Object -Last 6`
Expected: PASS.

- [ ] **Step 5: Ruff + Commit**

Ruff: `python -m ruff check deeptutor/api/routers/standards.py deeptutor/api/main.py tests/api/test_standards.py`

```bash
git add deeptutor/api/routers/standards.py deeptutor/api/main.py tests/api/test_standards.py
git commit -m "feat: GET /api/v1/standards 标注规范目录 (skill references 文档+章节)"
```

---

### Task 2: 前端标注规范库页面

**Files:**
- Create: `web/lib/standards-api.ts`
- Create: `web/app/(utility)/standards/page.tsx`
- Modify: `web/components/sidebar/SidebarShell.tsx`（Secondary NAV 加入口）
- Test: `web/tests/standards-api.test.ts`（如该目录有 node 测试模式）

- [ ] **Step 1: API 客户端**

Create `web/lib/standards-api.ts`:

```ts
export type StandardSection = string;

export type StandardDoc = {
  id: string;
  title: string;
  sections: string[];
  content: string;
};

export async function getStandards(): Promise<{ standards: StandardDoc[] }> {
  const res = await fetch("/api/v1/standards", { credentials: "include" });
  if (!res.ok) throw new Error(`Failed to load standards: ${res.status}`);
  return res.json();
}
```

Follow the fetch/error pattern used by `web/lib/learning-stats-api.ts`.

- [ ] **Step 2: 规范库页面**

Create `web/app/(utility)/standards/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { BookOpen, ChevronRight } from "lucide-react";
import { getStandards, type StandardDoc } from "@/lib/standards-api";

export default function StandardsPage() {
  const [docs, setDocs] = useState<StandardDoc[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getStandards()
      .then((r) => { if (!cancelled) setDocs(r.standards); })
      .catch(() => { if (!cancelled) setDocs([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return <div className="mx-auto max-w-3xl px-6 py-10 text-sm text-[var(--muted-foreground)]">加载中...</div>;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-6 py-8">
      <div className="flex items-center gap-2">
        <BookOpen className="h-5 w-5 text-blue-500" />
        <div>
          <h1 className="text-lg font-bold">标注规范库</h1>
          <p className="text-sm text-[var(--muted-foreground)]">数据标注行业标准与操作规范</p>
        </div>
      </div>
      {docs.length === 0 && (
        <p className="text-sm text-[var(--muted-foreground)]">暂无规范文档</p>
      )}
      {docs.map((doc) => (
        <div key={doc.id} className="rounded-2xl border border-[var(--border)] bg-[var(--card)]">
          <button
            type="button"
            onClick={() => setOpenId(openId === doc.id ? null : doc.id)}
            className="flex w-full items-center gap-2 px-4 py-3 text-left"
          >
            <ChevronRight className={`h-4 w-4 transition-transform ${openId === doc.id ? "rotate-90" : ""}`} />
            <span className="text-sm font-semibold">{doc.title}</span>
            <span className="ml-auto text-xs text-[var(--muted-foreground)]">{doc.sections.length} 章节</span>
          </button>
          {openId === doc.id && (
            <div className="border-t border-[var(--border)] px-4 py-3">
              <div className="mb-3 flex flex-wrap gap-1.5">
                {doc.sections.map((s) => (
                  <a key={s} href={`#${doc.id}-${s}`} className="rounded bg-[var(--muted)] px-2 py-0.5 text-xs text-[var(--muted-foreground)]">{s}</a>
                ))}
              </div>
              <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap font-mono text-xs leading-5 text-[var(--foreground)]">
                {doc.content}
              </pre>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
```

NOTE: rendering raw markdown as `<pre>` is acceptable for a first version; a later refinement could use RichMarkdownRenderer. Keep it simple.

- [ ] **Step 3: 侧边栏入口**

Read `web/components/sidebar/SidebarShell.tsx`, find the Secondary NAV (where 记忆/设置 are), add an entry:
- label 标注规范, href `/standards`, an icon (e.g. `BookOpen`)

Follow the exact structure used by the Memory/Settings entries (icon + label + href).

- [ ] **Step 4: 验证**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit` → 0 errors

If `web/tests/` has a node-test pattern for API clients (check `web/tests/learning-stats-api.test.ts` or similar), add a matching `standards-api.test.ts`. If no such pattern exists, skip (tsc + smoke covers it).

- [ ] **Step 5: Commit**

```bash
git add web/lib/standards-api.ts "web/app/(utility)/standards/page.tsx" web/components/sidebar/SidebarShell.tsx
git commit -m "feat: 标注规范库页 (文档列表+章节+全文) + 侧边栏入口"
```

---

### Task 3: 对话内 `〔规范: ...〕` 自动检测 → 可点击弹窗

**Files:**
- Modify: `web/components/common/RichMarkdownRenderer.tsx`
- Create: `web/components/common/StandardDialog.tsx`

- [ ] **Step 1: 创建 StandardDialog**

Create `web/components/common/StandardDialog.tsx` — a modal dialog that fetches standards (via getStandards) and shows a doc's section content:

```tsx
"use client";

import { useEffect, useState } from "react";
import { X, BookOpen } from "lucide-react";
import { getStandards, type StandardDoc } from "@/lib/standards-api";

export function StandardDialog({
  docId,
  section,
  onClose,
}: {
  docId: string;
  section?: string | null;
  onClose: () => void;
}) {
  const [doc, setDoc] = useState<StandardDoc | null>(null);
  useEffect(() => {
    let cancelled = false;
    getStandards().then((r) => {
      if (cancelled) return;
      const found = r.standards.find((d) => d.id === docId);
      setDoc(found ?? null);
    }).catch(() => { if (!cancelled) setDoc(null); });
    return () => { cancelled = true; };
  }, [docId]);

  if (!doc) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="max-h-[80vh] w-full max-w-2xl overflow-auto rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-blue-500" />
            <h3 className="text-sm font-bold">{doc.title}{section ? ` · ${section}` : ""}</h3>
          </div>
          <button type="button" onClick={onClose} aria-label="关闭">
            <X className="h-4 w-4" />
          </button>
        </div>
        <pre className="whitespace-pre-wrap font-mono text-xs leading-5 text-[var(--foreground)]">{doc.content}</pre>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 在 RichMarkdownRenderer 中检测 `〔规范: ...〕`**

Read `web/components/common/RichMarkdownRenderer.tsx` fully. Find where it processes text content (there's likely a `processMarkdownContent` or a pre-processing step near line 12, and the components mapping around line 573). Add a `StandardLink`/regex detection:

1. Add a regex to detect `〔规范:\s*([^〕§]+?)(?:§(.+?))?〕` in the raw markdown text BEFORE rendering.
2. Replace matches with a placeholder that the components mapping turns into a clickable `<button>` that opens `StandardDialog`.
3. Add state `const [standardRef, setStandardRef] = useState<{docId: string; section?: string} | null>(null)` at the component top.
4. In the components mapping, handle the placeholder → render a styled clickable chip "📖 {docId}{section ? ` §${section}` : ''}" that calls `setStandardRef({docId, section})`.
5. Render `{standardRef && <StandardDialog docId={standardRef.docId} section={standardRef.section} onClose={() => setStandardRef(null)} />}`.

IMPORTANT: The cleanest approach depends on how the file pre-processes text. Read it first. If it uses `processMarkdownContent` (from `@/lib/latex`) as a string pre-pass, add a similar pre-pass that replaces `〔规范: ...〕` with a sentinel token like `[STANDARD_REF:docId:section]`, then map that token in the `a`/custom component handling. If there's no pre-pass, use a ReactMarkdown `components` override or remark plugin. Match the existing architecture — do NOT force a pattern that doesn't fit.

- [ ] **Step 3: 验证**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit` → 0 errors

- [ ] **Step 4: Commit**

```bash
git add web/components/common/RichMarkdownRenderer.tsx web/components/common/StandardDialog.tsx
git commit -m "feat: 对话〔规范: 文档§章节〕引用可点击弹窗查看原文"
```

---

### Task 4: 验证

**Files:** none

- [ ] **Step 1: 后端测试**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_standards.py -q 2>&1 | Select-Object -Last 3`
Expected: PASS.

- [ ] **Step 2: 前端 tsc + build**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit` → 0 errors; `Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY -ErrorAction SilentlyContinue; npx next build 2>&1 | Select-Object -Last 4` → succeeds

- [ ] **Step 3: Playwright 冒烟**

With backend (8001) + frontend (3782) running:
1. Navigate to `/standards` → document cards render with titles + section counts
2. Click a doc → expands showing sections + full content
3. In a chat message containing `〔规范: bbox-guide§边界框绘制〕` → renders as clickable chip → click → StandardDialog opens with the doc content
4. Screenshot for record

- [ ] **Step 4: 提交修复（如有）**

If smoke found issues, fix + commit. Otherwise no commit.

---

## Self-Review

**1. Spec coverage:**
- §3 后端 /standards → Task 1
- §4 前端规范库页 → Task 2
- §5 对话检测 → Task 3
- §6 测试 → Task 4
✅ 全覆盖

**2. Placeholder scan:** 所有步骤含具体代码/命令。Task 3 Step 2 明确"读文件后用匹配现有架构的方式实现"（不强制模式）。✅

**3. Type consistency:** `StandardDoc`/`StandardSection` 类型 Task 2 Step 1 定义，Step 2/3 引用一致；`standards` 端点返回 `{"standards": [...]}` 与前端 `getStandards` 一致。✅

**已知风险（沿用 spec §8）：**
1. 文档全量返回 content 稍大（references 约 5 文件每 <5KB，可接受）
2. `〔规范: ...〕` 标记若不输出则检测不触发（退化纯文本，无副作用）
