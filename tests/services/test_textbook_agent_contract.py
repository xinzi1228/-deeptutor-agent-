from __future__ import annotations

import json
from pathlib import Path

from deeptutor.tools.delegate_expert_tool import EXPERT_TOOL_WHITELISTS

ROOT = Path(__file__).resolve().parents[2]


def test_textbook_skill_and_expert_enforce_review_only_contract() -> None:
    skill = (ROOT / "deeptutor/skills/builtin/textbook-analysis/SKILL.md").read_text(encoding="utf-8")
    contract = (ROOT / "deeptutor/skills/builtin/textbook-analysis/references/output-contract.md").read_text(encoding="utf-8")
    expert = (ROOT / "deeptutor/skills/builtin/annotation-coach-flows/references/experts/textbook_analyst.md").read_text(encoding="utf-8")

    for text in (skill, expert):
        assert "不得" in text or "禁止" in text
        assert "发布" in text
        assert "源页" in text
    assert "source_pages" in contract
    assert EXPERT_TOOL_WHITELISTS["textbook_analyst"] == ("textbook_candidate",)


def test_textbook_expert_is_indexed_in_manifest() -> None:
    path = ROOT / "deeptutor/skills/builtin/annotation-coach-flows/experts_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entry = next(row for row in manifest["experts"] if row["id"] == "textbook_analyst")
    assert entry["file"].endswith("textbook_analyst.md")
