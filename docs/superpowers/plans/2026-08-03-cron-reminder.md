# 定时学习提醒实施计划（cron 工具验证 + 提示词 + 端到端）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让定时学习提醒功能可信（补测试）+ 可演示（Coach 会主动用 cron 工具 + 端到端验证）。

**Architecture:** `cron` 工具已存在（schedule/list/cancel，always_on，`agentic_pipeline` 注入 `_cron_owner`，`execute_job` 到点用 Coach 生成提醒写进会话）。本计划 = 补测试（monkeypatch `get_cron_service`）+ PERSONA 教 Coach 用 + 端到端验证。不新写功能代码。

**Tech Stack:** Python pytest, markdown。

**Spec:** `docs/specs/cron-reminder-design.md`（已提交 `76fd78b0`）

---

### Task 1: 测试 `tests/tools/test_cron_tool.py`

**Files:**
- Create: `tests/tools/test_cron_tool.py`

- [ ] **Step 1: 读实现 + 写失败测试**

Read `deeptutor/tools/cron_tool.py` (142 lines) and `deeptutor/services/cron/service.py` (CronJob/CronOwner/CronSchedule/get_cron_service). Then create `tests/tools/test_cron_tool.py`:

```python
"""Cron tool — schedule/list/cancel timed tasks for a conversation."""

from __future__ import annotations

import uuid

import pytest

from deeptutor.services.cron import CronJob, CronOwner, CronSchedule
from deeptutor.tools.cron_tool import run_cron_action


class _FakeCronService:
    """In-memory cron service stand-in."""

    def __init__(self) -> None:
        self.jobs: dict[str, CronJob] = {}

    def list_jobs(self, owner_key: str | None = None) -> list[CronJob]:
        jobs = list(self.jobs.values())
        if owner_key is not None:
            jobs = [j for j in jobs if j.owner.key == owner_key]
        return sorted(jobs, key=lambda j: j.state.next_run_at_ms or 0)

    def add_job(self, **kwargs) -> CronJob:
        job = CronJob(
            id=uuid.uuid4().hex[:10],
            name=kwargs.get("name") or "",
            message=kwargs.get("message") or "",
            schedule=kwargs.get("schedule") or CronSchedule(kind="every", every_seconds=60),
            owner=kwargs.get("owner") or CronOwner(kind="chat"),
        )
        job.state.next_run_at_ms = 1
        self.jobs[job.id] = job
        return job

    def cancel_job(self, job_id: str, *, owner_key: str | None = None) -> bool:
        job = self.jobs.get(job_id)
        if job is None:
            return False
        if owner_key is not None and job.owner.key != owner_key:
            return False
        del self.jobs[job_id]
        return True


@pytest.fixture
def fake_service(monkeypatch):
    service = _FakeCronService()
    monkeypatch.setattr("deeptutor.tools.cron_tool.get_cron_service", lambda: service)
    return service


def _owner(**overrides) -> dict:
    base = {"kind": "chat", "session_id": "sess1", "user_id": "u1"}
    base.update(overrides)
    return base


def test_list_empty(fake_service):
    out = run_cron_action({"action": "list", "_cron_owner": _owner()})
    assert out.ok
    assert "No scheduled tasks" in out.text


def test_schedule_every_seconds(fake_service):
    out = run_cron_action({
        "action": "schedule",
        "_cron_owner": _owner(),
        "message": "该练标注了",
        "name": "学习提醒",
        "every_seconds": 30,
    })
    assert out.ok
    assert "Scheduled" in out.text
    assert len(fake_service.jobs) == 1
    job = list(fake_service.jobs.values())[0]
    assert job.message == "该练标注了"
    assert job.schedule.kind == "every"
    assert job.schedule.every_seconds == 30


def test_schedule_requires_message(fake_service):
    out = run_cron_action({"action": "schedule", "_cron_owner": _owner()})
    assert not out.ok
    assert "message" in out.text


def test_schedule_exactly_one_timing(fake_service):
    out = run_cron_action({
        "action": "schedule",
        "_cron_owner": _owner(),
        "message": "x",
        "at": "2026-06-12T09:00",
        "every_seconds": 30,
    })
    assert not out.ok
    assert "exactly one of" in out.text


def test_cancel_existing(fake_service):
    created = run_cron_action({
        "action": "schedule", "_cron_owner": _owner(),
        "message": "x", "every_seconds": 30,
    })
    assert created.ok
    job_id = created.meta["job_id"]
    out = run_cron_action({"action": "cancel", "_cron_owner": _owner(), "job_id": job_id})
    assert out.ok
    assert "cancelled" in out.text
    assert len(fake_service.jobs) == 0


def test_cancel_missing(fake_service):
    out = run_cron_action({"action": "cancel", "_cron_owner": _owner(), "job_id": "nope"})
    assert not out.ok


def test_no_owner_rejected():
    out = run_cron_action({"action": "list"})
    assert not out.ok
    assert "not available" in out.text


def test_schedule_blocked_inside_cron(fake_service):
    out = run_cron_action({
        "action": "schedule", "_cron_owner": _owner(),
        "message": "x", "every_seconds": 30, "_cron_in_context": True,
    })
    assert not out.ok
    assert "inside a running" in out.text
```

NOTE: read `deeptutor/services/cron/__init__.py` to confirm `CronJob/CronOwner/CronSchedule/get_cron_service` are exported from `deeptutor.services.cron`. If not, import from the module files directly.

- [ ] **Step 2: 运行测试确认通过**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_cron_tool.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS (the tool implementation exists, so tests should pass immediately — this is verification of existing behavior, not TDD for new code). If any test reveals a real bug in the tool, fix the tool and note it.

- [ ] **Step 3: Ruff + Commit**

Ruff: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m ruff check tests/tools/test_cron_tool.py`

```bash
git add tests/tools/test_cron_tool.py
git commit -m "test: cron 工具 schedule/list/cancel 测试 (fake 服务隔离)"
```

---

### Task 2: PERSONA 教 Coach 用 cron 工具

**Files:**
- Modify: `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` (+ sync workspace copy)

- [ ] **Step 1: 读现有交互规范**

Read `deeptutor/services/persona/presets/annotation-coach/PERSONA.md`, find the 交互规范 section (near line 246, where 引用标准 rule is).

- [ ] **Step 2: 加 cron 提醒规则**

In the 交互规范 section, add after the 引用标准 rule:

```markdown
- 用户要求定时提醒/预约时，用 `cron` 工具注册（action=schedule）：`every_seconds`（至少30秒，演示常用）或 `at`（ISO 8601 时间）。提醒文案写教学风格，如"该练标注了——上次在边界框上 F1 只有50%，今天巩固一下？"。可用 action=list 查看本会话已注册任务，action=cancel 取消。
```

- [ ] **Step 3: 同步 workspace 副本**

Apply the same edit to `data/user/workspace/personas/annotation-coach/PERSONA.md` (gitignored, runtime-effective).

- [ ] **Step 4: Commit**

```bash
git add deeptutor/services/persona/presets/annotation-coach/PERSONA.md
git commit -m "feat: PERSONA 教 Coach 用 cron 工具注册定时学习提醒"
```

---

### Task 3: 端到端验证

**Files:** none (verification)

- [ ] **Step 1: 后端测试回归**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_cron_tool.py -q 2>&1 | Select-Object -Last 3`
Expected: PASS.

- [ ] **Step 2: 重启后端 + 端到端实测**

Ensure backend (8001) running (restart to pick up PERSONA change). Then via Playwright (frontend on 3782):
1. Open `/home`, send: "30 秒后提醒我练标注"
2. Watch Coach's tool calls — it should call `cron` with action=schedule, every_seconds=30
3. Wait ~40s → the session should gain a new assistant message that is the Coach's proactive reminder (delivered by `_execute_chat_job`)
4. Verify the reminder is teaching-style Chinese
5. Screenshot for record

If Coach doesn't call the cron tool on first try, the reminder may need rephrasing (e.g. "帮我设个定时任务，30秒后提醒我练标注"). Try a couple of phrasings.

- [ ] **Step 3: 提交验证期间修复（如有）**

If verification found a bug (e.g. cron tool broken, _cron_owner not injected in chat path), fix + commit. Otherwise no commit.

---

## Self-Review

**1. Spec coverage:**
- §3 测试 → Task 1
- §4 PERSONA → Task 2
- §5 端到端 → Task 3
✅ 全覆盖

**2. Placeholder scan:** 所有步骤含具体代码/命令。Task 3 是验证（明确操作步骤 + 判定标准）。✅

**3. Type consistency:** `run_cron_action` 签名、`CronActionOutcome.ok/text/meta`、`_cron_owner` dict 结构在测试中与实现一致。✅

**已知风险（沿用 spec §7）：**
1. 端到端依赖 LLM 调用 cron 工具——Coach 不调则换措辞重试
2. 演示提醒 30s 间隔，会话需保持打开才能看到追加消息
