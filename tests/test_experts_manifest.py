"""experts_manifest.json consistency — index <-> directory + frontmatter."""

from __future__ import annotations

import json
from pathlib import Path
import re

BASE = Path(__file__).resolve().parents[1] / "deeptutor" / "skills" / "builtin" / "annotation-coach-flows"
MANIFEST_PATH = BASE / "experts_manifest.json"
EXPERT_DIR = BASE / "references" / "experts"
REQUIRED_FIELDS = ["id", "label", "icon", "color", "file"]


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


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


def test_manifest_exists():
    assert MANIFEST_PATH.exists()


def test_manifest_has_coordinator_and_11_experts():
    manifest = _load_manifest()
    assert "coordinator" in manifest
    assert manifest["coordinator"]["id"] == "annotation-coach"
    experts = manifest["experts"]
    assert len(experts) == 11


def test_manifest_entries_have_required_fields():
    manifest = _load_manifest()
    for entry in [manifest["coordinator"]] + manifest["experts"]:
        for field in REQUIRED_FIELDS:
            assert entry.get(field), f"manifest entry missing {field}: {entry}"


def test_manifest_files_exist():
    manifest = _load_manifest()
    for entry in [manifest["coordinator"]] + manifest["experts"]:
        p = BASE / entry["file"]
        assert p.exists(), f"manifest file missing: {entry['file']}"


def test_every_expert_file_in_manifest():
    files = {p.stem for p in EXPERT_DIR.glob("*.md")}
    manifest_ids = {e["id"] for e in _load_manifest()["experts"]}
    assert files == manifest_ids


def test_frontmatter_name_matches_manifest_id():
    manifest = _load_manifest()
    for entry in manifest["experts"]:
        fm = _frontmatter(EXPERT_DIR / f"{entry['id']}.md")
        assert fm.get("name") == entry["id"], f"{entry['id']} frontmatter name mismatch"


def test_coordinator_frontmatter_name_matches():
    manifest = _load_manifest()
    fm = _frontmatter(BASE / manifest["coordinator"]["file"])
    assert fm.get("name") == manifest["coordinator"]["id"], "coordinator frontmatter name mismatch"
