import json
from pathlib import Path

from deeptutor.services.content_governance.models import SourceRecordCreate
from scripts.build_annotation_review_manifest import build_manifest, classify_candidate


def test_candidate_classifier_never_blindly_replaces_standard_sections():
    action, sources, proposal = classify_candidate(
        "data/user/workspace/annotation_kb/04-质量管控/01-质检流程设计.md"
    )

    assert action == "verify_annotation_procedure_claim"
    assert sources == ["source_gbt_42755_2023"]
    assert "人工" in proposal
    assert "全局替换" not in proposal


def test_manifest_is_candidate_only_and_has_one_row_per_finding(tmp_path: Path):
    project = tmp_path / "project"
    target = project / "data" / "user" / "workspace" / "annotation_kb"
    target.mkdir(parents=True)
    (project / "README.md").write_text("GB/T 41867-2022\n", encoding="utf-8")
    (target / "a.md").write_text(
        "第一处 GB/T 41867-2022\n第二处 GB/T 41867-2022\n",
        encoding="utf-8",
    )

    manifest = build_manifest(project)

    assert manifest["candidate_count"] == 3
    assert manifest["formal_content_modified"] is False
    assert manifest["human_approval_count"] == 0
    assert all(row["status"] == "awaiting_human_review" for row in manifest["candidates"])


def test_checked_in_source_catalog_has_valid_types_and_all_candidate_refs_exist():
    project_root = Path(__file__).resolve().parents[2]
    catalog = json.loads(
        (project_root / "data/content-governance/source-catalog.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (project_root / "data/content-governance/review-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    source_ids = {source["id"] for source in catalog["sources"]}

    for source in catalog["sources"]:
        SourceRecordCreate.model_validate(source)
    assert all(
        set(candidate["proposed_source_ids"]).issubset(source_ids)
        for candidate in manifest["candidates"]
    )
