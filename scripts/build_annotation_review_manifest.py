from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from deeptutor.services.file_io import atomic_write_json, atomic_write_text  # noqa: E402
from scripts.audit_annotation_sources import audit_sources  # noqa: E402


def classify_candidate(path: str) -> tuple[str, list[str], str]:
    lowered = path.lower()
    if "02-行业标准/01-" in path:
        return (
            "rewrite_standard_overview",
            ["source_gbt_41867_2022", "source_gbt_42755_2023"],
            "重写整篇标准概述：41867 仅说明人工智能术语，数据标注流程另建 42755 概述；章节待合法全文人工核对。",
        )
    if any(token in path for token in ("安全", "合规")):
        return (
            "verify_security_scope",
            ["source_gbt_45674_2025"],
            "删除错误标准归因；先判断是否属于生成式人工智能数据标注安全场景，再决定是否引用 45674。",
        )
    if any(token in path for token in ("培训", "能力图谱", "competency_tree")) or "job_analysis" in lowered:
        return (
            "align_occupational_competency",
            ["source_mohrss_ai_trainer_2021"],
            "将岗位和培训能力改为人社部职业标准来源；保留项目课程映射时明确标记为教学设计。",
        )
    if any(token in lowered for token in ("persona.md", "resources.md", "standards-trace-design")):
        return (
            "replace_citation_example",
            ["source_gbt_42755_2023"],
            "把错误标准号示例改为 42755；在未核对全文前不保留虚构章节号。",
        )
    return (
        "verify_annotation_procedure_claim",
        ["source_gbt_42755_2023"],
        "移除对 41867 的流程或质量归因；由人工依据 42755 合法全文逐条核对，无法核实的阈值降级为项目经验。",
    )


def build_manifest(project_root: Path) -> dict:
    findings = audit_sources(project_root)
    candidates = []
    for finding in findings:
        action, sources, proposal = classify_candidate(str(finding["path"]))
        location = f"{finding['path']}:{finding['line']}"
        candidates.append(
            {
                "id": "candidate_" + sha256(location.encode("utf-8")).hexdigest()[:16],
                "content_location": location,
                "current_reference": finding["reference"],
                "risk": finding["risk"],
                "action": action,
                "proposed_source_ids": sources,
                "proposed_change": proposal,
                "status": "awaiting_human_review",
                "ai_generated": True,
                "reviewer": None,
                "reviewed_at": None,
            }
        )
    return {
        "schema_version": 1,
        "manifest_version": "2026.08.14-candidate.1",
        "source_catalog_version": "2026.08.14-candidate.1",
        "formal_content_modified": False,
        "human_approval_count": 0,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def build_report(manifest: dict) -> str:
    counts = Counter(candidate["action"] for candidate in manifest["candidates"])
    lines = [
        "# 标注专业内容来源审计报告（候选）",
        "",
        "> 状态：等待人工终审。本报告和清单由程序生成，未修改 60 篇正式资料、题库、评分规则或历史成绩。",
        "",
        "## 审计结论",
        "",
        f"- 共发现 {manifest['candidate_count']} 处 `GB/T 41867-2022` 高风险误引。",
        "- 官方页面确认该标准名称为《信息技术 人工智能 术语》，不能作为数据标注流程、质量阈值或人员要求的依据。",
        "- `GB/T 42755-2023` 可作为机器学习数据标注流程框架的候选来源，但具体章节、页码和阈值仍需取得合法全文后人工核对。",
        "- 生成式人工智能标注安全场景可候选关联 `GB/T 45674-2025`，不得泛化到全部标注任务。",
        "- 岗位能力和人员培训优先关联《人工智能训练师国家职业技能标准（2021年版）》。",
        "",
        "## 候选修订分类",
        "",
    ]
    for action, count in sorted(counts.items()):
        lines.append(f"- `{action}`：{count} 处")
    lines.extend(
        [
            "",
            "## 人工终审步骤",
            "",
            "1. 取得具有合法使用权的标准全文和教材原文件。",
            "2. 逐条核对章节、页码、定义、阈值和适用范围，不执行全局替换。",
            "3. 无法获得权威依据的教学内容标记为“项目经验”或“示例阈值”。",
            "4. 审核通过后通过内容治理 API 发布新版本，并保留旧答题和初次成绩。",
            "5. 随机抽取不少于 20 道题，复核答案、解析、来源和界面引用是否一致。",
            "",
            "## 官方身份来源",
            "",
            "- GB/T 41867-2022：https://std.samr.gov.cn/gb/search/gbDetailed?id=EB58F4DA9092B2A2E05397BE0A0A7D33",
            "- GB/T 42755-2023：https://std.samr.gov.cn/gb/search/gbDetailed?id=FC816D04FEB462EBE05397BE0A0AD5FA",
            "- GB/T 45674-2025：https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=407584DD0FA2BA19E62E85D3469290B0",
            "- 人工智能训练师国家职业技能标准（2021年版）：https://www.mohrss.gov.cn/xxgk2020/fdzdgknr/rcrs_4225/jnrc/202112/W020211227626977039770.pdf",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    manifest = build_manifest(project_root)
    atomic_write_json(
        project_root / "data" / "content-governance" / "review-manifest.json",
        manifest,
    )
    atomic_write_text(
        project_root / "docs" / "content-audit" / "annotation-content-audit-report.md",
        build_report(manifest),
    )
    print(f"已生成 {manifest['candidate_count']} 条待人工审核候选；正式内容未修改。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
