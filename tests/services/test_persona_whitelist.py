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


def test_load_for_context_defaults_to_annotation_coach(tmp_path: Path) -> None:
    from deeptutor.services.persona.service import DEFAULT_PERSONA, PersonaService

    service = PersonaService(root=tmp_path / "personas")
    service.create(DEFAULT_PERSONA, "Annotation Coach", "Guide annotation practice.")
    rendered = service.load_for_context("")
    assert "### Persona: annotation-coach" in rendered
