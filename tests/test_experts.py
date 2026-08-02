"""Expert role files — frontmatter completeness + id/name/file consistency."""

from __future__ import annotations

from pathlib import Path
import re

EXPERT_DIR = Path(__file__).resolve().parents[1] / "deeptutor" / "skills" / "builtin" / "annotation-coach-flows" / "references" / "experts"

EXPECTED_EXPERTS = [
    "learning_planner", "session_steward", "task_guide",
    "struggle_detective", "report_analyst", "grading_expert",
]

REQUIRED_FRONTMATTER = ["name", "description", "color", "emoji", "vibe"]


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result


def test_expert_files_exist():
    for eid in EXPECTED_EXPERTS:
        assert (EXPERT_DIR / f"{eid}.md").exists(), f"missing expert file {eid}.md"


def test_no_extra_expert_files():
    files = {p.stem for p in EXPERT_DIR.glob("*.md")}
    assert files == set(EXPECTED_EXPERTS)


def test_frontmatter_complete():
    for eid in EXPECTED_EXPERTS:
        fm = _frontmatter(EXPERT_DIR / f"{eid}.md")
        for field in REQUIRED_FRONTMATTER:
            assert fm.get(field), f"{eid}.md missing frontmatter field: {field}"


def test_frontmatter_name_matches_filename():
    for eid in EXPECTED_EXPERTS:
        fm = _frontmatter(EXPERT_DIR / f"{eid}.md")
        assert fm.get("name") == eid, f"{eid}.md frontmatter name mismatch"


def test_expert_sections_present():
    for eid in EXPECTED_EXPERTS:
        text = (EXPERT_DIR / f"{eid}.md").read_text(encoding="utf-8")
        for section in ["身份", "使命", "规则", "能力", "流程"]:
            assert section in text, f"{eid}.md missing section: {section}"
