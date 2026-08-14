from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

HIGH_RISK_PATTERNS = {
    "misidentified_standard_gbt_41867_2022": re.compile(r"GB/T\s*41867-2022", re.IGNORECASE),
}
SCAN_SUFFIXES = {".md", ".json", ".py", ".yaml", ".yml"}
DEFAULT_TARGETS = (
    "README.md",
    "data/user/workspace/annotation_kb",
    "data/user/workspace/competency_tree.json",
    "data/user/workspace/personas/annotation-coach",
    "deeptutor/services/persona/presets/annotation-coach",
    "deeptutor/skills/builtin/annotation-coach-flows",
    "deeptutor/skills/builtin/annotation-guide",
    "deeptutor/tools",
    "docs/specs",
)


def audit_sources(project_root: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for target_name in DEFAULT_TARGETS:
        target = project_root / target_name
        paths = [target] if target.is_file() else sorted(target.rglob("*")) if target.exists() else []
        for path in paths:
            if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line_number, line in enumerate(lines, start=1):
                for rule_id, pattern in HIGH_RISK_PATTERNS.items():
                    if pattern.search(line):
                        findings.append(
                            {
                                "rule_id": rule_id,
                                "risk": "critical",
                                "path": path.relative_to(project_root).as_posix(),
                                "line": line_number,
                                "reference": "GB/T 41867-2022",
                                "action": "人工核对真实来源；禁止盲目全局替换",
                            }
                        )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="只读审计标注资料中的高风险来源引用")
    parser.add_argument("--check-only", action="store_true", help="只报告，不修改任何文件")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    findings = audit_sources(project_root)
    if args.json:
        print(json.dumps({"finding_count": len(findings), "findings": findings}, ensure_ascii=False, indent=2))
    else:
        print(f"内容来源审计：发现 {len(findings)} 处高风险引用。")
        for finding in findings:
            print(
                f"- [{finding['risk']}] {finding['path']}:{finding['line']} "
                f"{finding['reference']} — {finding['action']}"
            )
        print("本次为只读检查，未修改任何资料或题目。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
