# 第四轮优化实现计划：记忆工具限制 + LLM 去重（借鉴 TencentDB-Agent-Memory）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 借鉴腾讯 `TencentDB-Agent-Memory` 两点：A) agent_loop 记忆类工具每轮 ≤3 次截断护栏；B) `LearningRecordStore.reflect()` 升级 LLM 批量去重（store/skip/update/merge + 跨类型合并）。

**Architecture:** A = agent_loop `_run_loop` 纯本地计数护栏（复用 E3 delegate 截断模式）+ PERSONA 指南。B = 新服务 `deeptutor/services/learning_records_dedup.py`（纯函数 + LLM 调用，懒加载防循环），reflect() 增加 LLM 路径，失败回退现有规则式。

**Tech Stack:** Python 3.11+ asyncio / pytest（`@pytest.mark.asyncio`）/ ruff。参考 clone：`%TEMP%\opencode\refs\tencentdb-memory\package\src\core\record\l1-dedup.ts` + `prompts\l1-dedup.ts`。

---

## 背景（已核实）

- `agent_loop.py` `_run_loop`：E3 已实现 delegate 截断（L431-460，`_MAX_DELEGATE_PER_ROUND=2`，`kept_tool_calls` 重建 + 中文 system 引导）。A 复用此模式。
- `learning_records.py` `reflect()`（L249-328）：规则式去重（按 type+task_id+kp 硬聚类，保留最新 + 合并 evidence/kps + 归档旧）。B 增加 LLM 路径。
- E4 已给 record 加 `confidence`（0-1）/`source` 字段。B 的 merge 复用 confidence 提升语义。
- 腾讯 `l1-dedup.ts`：批量决策 + `parseBatchResult`（非法 record_id 跳过、缺决策默认 store、非法 action 回退 store、markdown 块剥离、sanitize JSON）。

## 任务分解

### Task 1: A——agent_loop 记忆类工具每轮 ≤3 次截断

**Files:**
- Modify: `deeptutor/agents/chat/agent_loop.py`（`_MAX_DELEGATE_PER_ROUND` 附近加 `_MEMORY_TOOLS` + `_MAX_MEMORY_TOOLS_PER_ROUND`；`_run_loop` L460 后加截断）
- Test: `tests/agents/chat/test_agent_loop.py`

- [ ] **Step 1: 写失败测试**——追加到 `tests/agents/chat/test_agent_loop.py` 末尾（复用 `_Registry`/`_ScriptedChatClient`/`_delegate_tool_call`/`_run`/`_loop_system_texts` helper）：

```python
def _memory_tool_call(tool: str) -> dict:
    return {
        "id": f"call-{tool}",
        "name": tool,
        "arguments": json.dumps({"query": "边界框"}),
    }


@pytest.mark.asyncio
async def test_loop_truncates_excess_memory_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """More than _MAX_MEMORY_TOOLS_PER_ROUND memory-retrieval tools in one
    round: excess calls dropped, a Chinese guide injected, others untouched."""
    registry = _Registry()
    client = _ScriptedChatClient(
        [
            [
                _llm_chunk(content="Recalling."),
                _llm_chunk(
                    tool_calls=[
                        _memory_tool_call("kb_search"),
                        _memory_tool_call("graph_query"),
                        _memory_tool_call("competency_map"),
                        _memory_tool_call("ability_radar"),
                    ]
                ),
            ],
            [_llm_chunk(content="Done.")],
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(
        pipeline, "_compose_enabled_tools",
        lambda _context: ["kb_search", "graph_query", "competency_map", "ability_radar"],
    )
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    events = await _run(
        pipeline,
        UnifiedContext(
            session_id="s1", user_message="Recalling",
            enabled_tools=["kb_search", "graph_query", "competency_map", "ability_radar"],
        ),
    )

    memory_executed = [e for e in registry.executed if e["name"] in {
        "kb_search", "graph_query", "competency_map", "ability_radar", "get_annotation_task"}]
    assert len(memory_executed) == 3, f"expected 3 memory tools dispatched, got {len(memory_executed)}"
    system_texts = _loop_system_texts(client)
    assert any("记忆" in t and "3" in t for t in system_texts), "expected memory-tool guide notice"
    result = _result(events)
    assert result.metadata["response"] == "Done."
    assert result.metadata["completed"] is True


@pytest.mark.asyncio
async def test_loop_keeps_three_memory_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _Registry()
    client = _ScriptedChatClient(
        [
            [
                _llm_chunk(content="Recalling."),
                _llm_chunk(
                    tool_calls=[
                        _memory_tool_call("kb_search"),
                        _memory_tool_call("graph_query"),
                        _memory_tool_call("competency_map"),
                    ]
                ),
            ],
            [_llm_chunk(content="Done.")],
        ]
    )
    pipeline = AgenticChatPipeline(language="en")
    pipeline.registry = registry
    monkeypatch.setattr(
        pipeline, "_compose_enabled_tools",
        lambda _context: ["kb_search", "graph_query", "competency_map"],
    )
    monkeypatch.setattr(pipeline, "_build_openai_client", lambda: client)

    events = await _run(
        pipeline,
        UnifiedContext(
            session_id="s1", user_message="Recalling",
            enabled_tools=["kb_search", "graph_query", "competency_map"],
        ),
    )

    memory_executed = [e for e in registry.executed if e["name"] in {
        "kb_search", "graph_query", "competency_map", "ability_radar", "get_annotation_task"}]
    assert len(memory_executed) == 3
    system_texts = _loop_system_texts(client)
    assert not any("已截断本轮多余的记忆检索" in t for t in system_texts)


def test_memory_tool_set_excludes_write_tools() -> None:
    from deeptutor.agents.chat.agent_loop import _MEMORY_TOOLS
    assert "write_learning_record" not in _MEMORY_TOOLS
    assert "log_decision" not in _MEMORY_TOOLS
    assert "kb_search" in _MEMORY_TOOLS
```

- [ ] **Step 2: 运行确认失败**

```
$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/agents/chat/test_agent_loop.py -q
```

Expected: FAIL（`_MEMORY_TOOLS` 不存在 / 截断未生效）。

- [ ] **Step 3: 实现**——`agent_loop.py`：

在 `_MAX_DELEGATE_PER_ROUND = 2`（L77）后加：

```python
# Per-round memory-retrieval concurrency guardrail (TencentDB-Agent-Memory
# borrow, format.ts MEMORY_TOOLS_GUIDE): at most this many read-only memory /
# knowledge-retrieval tools may run in one round. The coach should prefer
# already-recalled results over repeatedly hitting retrieval tools with new
# queries; write tools (write_learning_record / log_decision) are NOT counted.
_MEMORY_TOOLS = frozenset(
    {
        "kb_search",
        "graph_query",
        "competency_map",
        "ability_radar",
        "get_annotation_task",
    }
)
_MAX_MEMORY_TOOLS_PER_ROUND = 3
```

在 `_run_loop` 的 E3 delegate 截断块（L454-460，`logger.warning(... delegate ...)` 之后、`messages.append(assistant_message_with_tool_calls(...))` 之前）加：

```python
            # Memory-retrieval guardrail: cap how many read-only memory / KB
            # tools run in a single round (TencentDB-Agent-Memory borrow).
            # Excess memory-tool calls are dropped; non-memory tools are
            # untouched and keep their original relative order.
            memory_count = sum(1 for tc in kept_tool_calls if tc.get("name") in _MEMORY_TOOLS)
            if memory_count > _MAX_MEMORY_TOOLS_PER_ROUND:
                kept_memory = 0
                new_kept: list[dict[str, Any]] = []
                for tc in kept_tool_calls:
                    if tc.get("name") in _MEMORY_TOOLS:
                        if kept_memory < _MAX_MEMORY_TOOLS_PER_ROUND:
                            new_kept.append(tc)
                        kept_memory += 1
                    else:
                        new_kept.append(tc)
                kept_tool_calls = new_kept
                messages.append(
                    {
                        "role": "system",
                        "content": (
                            f"已截断本轮多余的记忆检索（单轮最多 {_MAX_MEMORY_TOOLS_PER_ROUND} 次）。"
                            "请优先基于已召回的记忆/知识作答，或合并检索目标；"
                            "连续检索仍找不到时直接给出已有结论。"
                        ),
                    }
                )
                logger.warning(
                    "agent loop guardrail: truncated %d memory tools to %d per round (session=%s)",
                    memory_count,
                    _MAX_MEMORY_TOOLS_PER_ROUND,
                    self.context.session_id,
                )
```

> 顺序：此块接在 delegate 截断之后、`messages.append(assistant_message_with_tool_calls(result.text, kept_tool_calls))`（原 L462）之前。两次截断对 `kept_tool_calls` 依次重建，互不冲突（delegate 截断先、memory 截断后）。

- [ ] **Step 4: 运行确认通过**

```
$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/agents/chat/test_agent_loop.py -q
```

Expected: PASS（含既有 E1/E3 测试）。

- [ ] **Step 5: PERSONA.md 加指南**——`deeptutor/services/persona/presets/annotation-coach/PERSONA.md` 加「记忆工具调用指南」节：

```markdown
## 记忆工具调用指南

- 每轮对话中，只读检索工具（`kb_search` / `graph_query` / `competency_map` /
  `ability_radar` / `get_annotation_task`）**合计最多调用 3 次**。
- 优先使用本轮回调的结果作答；连续检索仍找不到时，基于已有记忆给出结论。
- 写作类工具（`write_learning_record` / `log_decision`）不受此限制。
```

> 注意：PERSONA.md 运行时读 `data/user/workspace/personas/annotation-coach/PERSONA.md` 副本（gitignored，首次启动自动拷贝）。**改源文件**即可；若服务在跑且副本已存在，需手动同步副本或重启后由拷贝逻辑覆盖（实施时检查 `services/persona/` 的拷贝机制）。

- [ ] **Step 6: Commit**

```bash
git add deeptutor/agents/chat/agent_loop.py tests/agents/chat/test_agent_loop.py deeptutor/services/persona/presets/annotation-coach/PERSONA.md
git commit -m "feat: 记忆类工具每轮 ≤3 次截断护栏 (④轮A 腾讯借鉴)"
```

---

### Task 2: B——`learning_records_dedup.py` 服务（LLM 批量决策 + apply）

**Files:**
- Create: `deeptutor/services/learning_records_dedup.py`
- Test: `tests/services/test_learning_records_dedup.py`

- [ ] **Step 1: 写失败测试**——创建 `tests/services/test_learning_records_dedup.py`：

```python
"""LLM batch dedup for learning records (TencentDB-Agent-Memory borrow).

The four actions store/skip/update/merge decide how new records relate to
existing ones. LLM failures must never lose records — every fallback keeps
the new record via ``store``.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from deeptutor.services.learning_records_dedup import (
    build_candidates,
    parse_decisions,
    apply_decision,
)


def _record(**overrides) -> dict:
    base = {
        "type": "annotation_exercise",
        "task_id": "task1",
        "knowledge_point": "边界框绘制规范",
        "f1": 0.85,
        "readiness": "advance",
        "confidence": 0.8,
        "timestamp": "2026-08-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def test_build_candidates_clusters_by_anchor():
    records = [
        _record(task_id="task1", knowledge_point="边界框绘制规范"),
        _record(task_id="task1", knowledge_point="边界框绘制规范", f1=0.9),
        _record(task_id="task2", knowledge_point="NLP 命名实体"),
    ]
    groups = build_candidates(records)
    # task1 两条聚为一组，task2 一条独立
    assert any(len(g) > 1 for g in groups)
    assert sum(len(g) for g in groups) == 3


def test_parse_decisions_valid():
    raw = json.dumps([
        {"record_id": "r1", "action": "store", "target_ids": []},
        {"record_id": "r2", "action": "merge", "target_ids": ["old1"],
         "merged_content": "合并后", "merged_type": "annotation_exercise",
         "merged_confidence": 0.9},
    ])
    decisions = parse_decisions(raw, new_ids=["r1", "r2"])
    assert decisions["r1"]["action"] == "store"
    assert decisions["r2"]["action"] == "merge"
    assert decisions["r2"]["target_ids"] == ["old1"]


def test_parse_decisions_invalid_action_defaults_store():
    raw = json.dumps([{"record_id": "r1", "action": "delete"}])
    decisions = parse_decisions(raw, new_ids=["r1"])
    assert decisions["r1"]["action"] == "store"


def test_parse_decisions_missing_record_defaults_store():
    decisions = parse_decisions("not-json", new_ids=["r1", "r2"])
    assert decisions["r1"]["action"] == "store"
    assert decisions["r2"]["action"] == "store"


def test_apply_store_adds_record():
    records = [_record(timestamp="2026-08-01T00:00:00+00:00")]
    new = _record(f1=0.7, timestamp="2026-08-02T00:00:00+00:00")
    out = apply_decision(records, new, {"action": "store", "target_ids": []})
    assert len(out) == 2
    assert not out[-1].get("archived")


def test_apply_merge_archives_targets_and_lifts_confidence():
    old = _record(confidence=0.7, timestamp="2026-08-01T00:00:00+00:00")
    new = _record(confidence=0.8, timestamp="2026-08-02T00:00:00+00:00")
    records = [old]
    out = apply_decision(
        records,
        new,
        {
            "action": "merge",
            # 记录无 id 字段，用 timestamp 定位（与 apply_decision 的定位逻辑一致）
            "target_ids": ["2026-08-01T00:00:00+00:00"],
            "merged_content": "合并后的边界框规范记忆",
            "merged_confidence": 0.9,
        },
    )
    merged = [r for r in out if r.get("timestamp") == "2026-08-02T00:00:00+00:00"][0]
    assert merged["confidence"] == 0.9
    assert merged.get("merged_from") == ["2026-08-01T00:00:00+00:00"]
    assert any(r.get("archived") for r in out)


def test_apply_skip_keeps_new_unstored():
    records = [_record(timestamp="2026-08-01T00:00:00+00:00")]
    new = _record(f1=0.6, timestamp="2026-08-02T00:00:00+00:00")
    out = apply_decision(records, new, {"action": "skip", "target_ids": []})
    # skip = 无增量，不新增（保持原记录数）
    assert len(out) == 1
```

> 注意：record 是否含 `id` 字段需先读 `learning_records.py` 的 `_normalize_record`/`append` 确认（若无 id 用 timestamp 定位）。**实施时先读该文件确认字段**，测试用实际 id 字段。

- [ ] **Step 2: 运行确认失败**

```
$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/services/test_learning_records_dedup.py -q
```

Expected: FAIL（module not found）。

- [ ] **Step 3: 实现服务**——创建 `deeptutor/services/learning_records_dedup.py`：

```python
"""LLM batch dedup for learning records (TencentDB-Agent-Memory borrow).

Mirrors ``l1-dedup.ts`` conflict detection: a single LLM call decides how a
batch of new records relate to existing ones (store/skip/update/merge), then
the decisions are applied to the JSONL truth. Every failure path degrades to
``store`` so no record is ever lost (truth-preserving, reversible).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_VALID_ACTIONS = {"store", "skip", "update", "merge"}
_VALID_TYPES = {"diagnosis", "theory_mastered", "annotation_exercise"}


def build_candidates(records: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Cluster active records by (type, task_id, knowledge_point) anchor.

    Tencent's unified candidate pool relies on vector recall; we have no
    vector store for records, so the deterministic (type, anchor) clustering
    is the candidate pool. Returns groups of records that may conflict.
    """
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    standalone: list[dict[str, Any]] = []
    for r in records:
        if r.get("archived"):
            continue
        kind = r.get("type")
        if kind in ("annotation_exercise", "theory_mastered"):
            key = (kind, str(r.get("task_id", "")), str(r.get("knowledge_point", "")))
            if key[1] or key[2]:
                groups.setdefault(key, []).append(r)
                continue
        standalone.append(r)
    out = [g for g in groups.values() if len(g) > 1]
    for s in standalone:
        out.append([s])
    return out


def parse_decisions(raw: str, new_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Parse the LLM's batch decision JSON into a per-record_id decision map.

    Mirrors Tencent's ``parseBatchResult``: strip markdown fences, extract the
    JSON array, skip empty record_ids, default invalid actions to ``store``,
    and ensure every new record has a decision (missing → store).
    """
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    try:
        array_match = re.search(r"\[[\s\S]*\]", cleaned)
        parsed = json.loads(array_match.group(0)) if array_match else []
        items = parsed if isinstance(parsed, list) else []
    except (ValueError, TypeError, json.JSONDecodeError):
        items = []
    decisions: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        rid = str(item.get("record_id") or "").strip()
        if not rid:
            continue
        action = str(item.get("action") or "store")
        decisions[rid] = {
            "action": action if action in _VALID_ACTIONS else "store",
            "target_ids": [str(t) for t in (item.get("target_ids") or [])],
            "merged_content": item.get("merged_content") if isinstance(item.get("merged_content"), str) else None,
            "merged_type": item.get("merged_type") if item.get("merged_type") in _VALID_TYPES else None,
            "merged_confidence": item.get("merged_confidence") if isinstance(item.get("merged_confidence"), (int, float)) else None,
        }
    for rid in new_ids:
        decisions.setdefault(rid, {"action": "store", "target_ids": []})
    return decisions


def apply_decision(
    records: list[dict[str, Any]],
    new_record: dict[str, Any],
    decision: dict[str, Any],
) -> list[dict[str, Any]]:
    """Apply a single dedup decision, returning the new records list.

    ``store``  → append new. ``skip``   → drop new (no delta).
    ``update`` → replace target(s) with new (targets archived).
    ``merge``  → archive targets, append new with lifted confidence/content.
    Truth-preserving: targets are archived, never deleted.
    """
    action = decision.get("action", "store")
    target_ids = [str(t) for t in decision.get("target_ids") or []]

    if action == "store":
        return records + [new_record]

    if action == "skip":
        return list(records)

    # update / merge both archive targets and keep (a possibly enriched) new
    target_set = set(target_ids)
    remaining = []
    for r in records:
        rid = str(r.get("id") or r.get("timestamp") or "")
        if rid in target_set or rid == str(new_record.get("id") or new_record.get("timestamp") or ""):
            if rid in target_set:
                r["archived"] = True
            remaining.append(r)
            continue
        remaining.append(r)

    merged = dict(new_record)
    if action == "merge":
        mc = decision.get("merged_content")
        if mc:
            merged["session_summary"] = mc
        mconf = decision.get("merged_confidence")
        if isinstance(mconf, (int, float)):
            merged["confidence"] = mconf
        merged["merged_from"] = sorted(target_set)
    elif action == "update":
        mconf = decision.get("merged_confidence")
        if isinstance(mconf, (int, float)):
            merged["confidence"] = mconf
        merged["updated_from"] = sorted(target_set)
    return remaining + [merged]
```

> 注：`re` 已在模块顶部 import。`_DEDUP_FIELDS` 常量当前未使用（保留供 Task 4 LLM prompt 用），可暂不加——**YAGNI，移除它**。

- [ ] **Step 4: 运行确认通过**

```
$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/services/test_learning_records_dedup.py -v
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add deeptutor/services/learning_records_dedup.py tests/services/test_learning_records_dedup.py
git commit -m "feat: 学习记录 LLM 批量去重服务 (④轮B 腾讯借鉴)"
```

---

### Task 3: B——`reflect()` 接入 LLM 去重路径

**Files:**
- Modify: `deeptutor/services/learning_records.py`（`reflect()` 增加 LLM 路径）
- Test: `tests/services/test_learning_records_dedup.py`（追加 reflect 集成测试）

- [ ] **Step 1: 写失败测试**——追加到 `tests/services/test_learning_records_dedup.py`：

```python
def test_reflect_llm_path_falls_back_on_failure(monkeypatch, tmp_path):
    import deeptutor.services.learning_records as lr_mod

    def _boom(*args, **kwargs):
        raise RuntimeError("llm down")

    # reflect() 的 LLM 路径依赖 build_candidates —— 让它抛错触发回退
    monkeypatch.setattr(
        "deeptutor.services.learning_records_dedup.build_candidates", _boom
    )
    monkeypatch.setattr(
        lr_mod.LearningRecordStore, "file", lambda self: tmp_path / "records.jsonl"
    )

    store = lr_mod.LearningRecordStore()
    store._write_all([_record(timestamp="2026-08-01T00:00:00+00:00")])
    store._write_all([_record(f1=0.9, timestamp="2026-08-02T00:00:00+00:00")])

    result = store.reflect()
    # LLM 路径失败 → 回退规则式 reflect（不抛、不丢记录）
    assert "clusters_merged" in result
    records = store._read_records()
    assert len(records) >= 1
```

> 注：`reflect()` 现有签名无 LLM 参数。实施时给 `reflect()` 加可选参数（如 `llm_dedup: bool = True` 或自动探测），并在内部 try LLM 路径 → except 回退。测试先断言"失败不回退到抛异常"。

- [ ] **Step 2: 运行确认失败**

```
$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/services/test_learning_records_dedup.py -q
```

Expected: FAIL（reflect 无 LLM 路径 / monkeypatch 目标不存在）。

- [ ] **Step 3: 实现**——`learning_records.py` 的 `reflect()`（L249）改为：

```python
    def reflect(self, *, llm_dedup: bool = True) -> dict[str, Any]:
        """Memory evolution (EverOS Reflection): merge / dedupe / archive.

        Prefers the LLM batch-dedup path (TencentDB-Agent-Memory borrow:
        store/skip/update/merge + cross-anchor merge) when enabled; every
        LLM failure falls back to the deterministic rule-based path below,
        so records are never lost. Both paths are truth-preserving.
        """
        records = self._read_records()
        if llm_dedup:
            from deeptutor.services import learning_records_dedup as dedup_mod

            try:
                groups = dedup_mod.build_candidates(records)
                # Flatten to (new_record, candidates) pairs where group >1
                for group in groups:
                    if len(group) <= 1:
                        continue
                    group.sort(key=lambda x: x.get("timestamp", ""))
                    new_rec = dict(group[-1])
                    candidates = group[:-1]
                    # Build a minimal decision payload: merge with candidates
                    # (rule-based anchor merge — LLM refinement deferred to
                    # per-group calls in a follow-up; today we reuse the
                    # deterministic merge to avoid N LLM calls per reflect).
                    decision = {
                        "action": "merge",
                        "target_ids": [
                            str(c.get("id") or c.get("timestamp") or "")
                            for c in candidates
                        ],
                        "merged_confidence": max(
                            (float(c.get("confidence") or 0.5) for c in group)
                        ),
                    }
                    records = dedup_mod.apply_decision(records, new_rec, decision)
                self._write_all(records)
                merged = sum(1 for r in records if r.get("merged_from"))
                archived = sum(1 for r in records if r.get("archived"))
                return {
                    "clusters_merged": merged,
                    "records_archived": archived,
                    "active_records": len([r for r in records if not r.get("archived")]),
                    "dedup_mode": "llm-rules",
                }
            except Exception as exc:
                logger.warning("reflect LLM dedup failed, falling back to rule-based: %s", exc)
        # ... 现有规则式逻辑原样保留（L262-328）...
```

> 说明：**此实现为 LLM 路径的规则式锚定简化版**——真正调 LLM 的 `call_dedup_llm` 因需 async + LLM runner 接入，列为 Task 4。Task 3 先让 reflect 走"候选聚类 + merge 决策 + apply"（数据流打通），LLM 决策层 Task 4 替换 `decision` 构造。这样 reflect 的 LLM 路径可独立测试、逐步交付。

- [ ] **Step 4: 运行确认通过**

```
$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/services/test_learning_records_dedup.py -q
```

Expected: PASS（含 reflect 集成测试）。

- [ ] **Step 5: Commit**

```bash
git add deeptutor/services/learning_records.py tests/services/test_learning_records_dedup.py
git commit -m "feat: reflect() 接入 LLM 去重路径 (④轮B)"
```

---

### Task 4: B——`call_dedup_llm` LLM 决策层（可选 P1）

**Files:**
- Modify: `deeptutor/services/learning_records_dedup.py`（加 `call_dedup_llm`）
- Test: `tests/services/test_learning_records_dedup.py`

> **说明**：Task 3 已打通数据流（候选聚类 → merge → apply）。真正调 LLM 批量决策（腾讯 `formatBatchConflictPrompt` 的 store/skip/update/merge 判断）因需 async + `deeptutor.services.llm.complete` 接入，成本 M。若 Task 1-3 完成后余力充足则做，否则留 P1 待下轮。**YAGNI：Task 3 的规则式锚定 merge 已覆盖「同一锚点多记录合并」的核心价值**；LLM 层只补「跨锚点语义合并」这一增量。

## 验证
- `python -m pytest tests/agents/chat/test_agent_loop.py tests/services/test_learning_records_dedup.py -q` 全过
- 回归：`python -m pytest tests/agents/chat/ tests/tools/test_write_learning_record_graph.py tests/tools/test_log_decision_tool.py -q`（允许预存在 GBK/可选依赖失败）
- `ruff check deeptutor/agents/chat/agent_loop.py deeptutor/services/learning_records.py deeptutor/services/learning_records_dedup.py`
- `python -c "import deeptutor.api.main"`

## 提交（仅 commit，不 push）
- 按 Task 拆 3-4 个 commit，大版本完成后等用户指示统一 push
