"""Build RAG knowledge base from annotation_kb markdown files."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

KB_DIR = Path(__file__).parent.parent / "data" / "user" / "workspace" / "annotation_kb"


def build_annotation_kb(kb_name: str = "annotation-kb") -> tuple[int, str]:
    """Import all markdown files from annotation_kb/ into a LlamaIndex knowledge base.

    Returns (num_docs, message).
    """
    from deeptutor.services.rag.factory import get_rag_pipeline
    from deeptutor.services.rag.models import DocumentChunk, SourceDocument

    if not KB_DIR.exists():
        return 0, f"KB directory not found: {KB_DIR}"

    docs = []
    for md_file in sorted(KB_DIR.rglob("*.md")):
        rel_path = md_file.relative_to(KB_DIR)
        try:
            text = md_file.read_text(encoding="utf-8")
            if not text.strip():
                continue
            category = rel_path.parts[0] if len(rel_path.parts) > 1 else "other"
            docs.append(
                SourceDocument(
                    id=str(rel_path),
                    title=md_file.stem,
                    content=text,
                    metadata={"category": category, "path": str(rel_path)},
                )
            )
        except Exception as e:
            logger.warning(f"Skipping {md_file}: {e}")

    if not docs:
        return 0, "No valid documents found"

    pipeline = get_rag_pipeline()
    pipeline.create_index(kb_name, docs)

    return len(docs), f"Successfully indexed {len(docs)} documents into '{kb_name}'"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count, msg = build_annotation_kb()
    print(f"{msg} ({count} docs)")
