"""Write learning record tool — persists structured synapse records.

The annotation-coach persona writes one record after each diagnosis, after
each theory concept is mastered, and after each practice task is evaluated.
Records live in the per-user JSONL learning store (see
:mod:`deeptutor.services.learning_records`) and drive the /progress
dashboard. A compact summary is mirrored into L3 recent.md so the coach can
resume from the last checkpoint on the next conversation.
"""

from __future__ import annotations

import json
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.tools.prompting import load_prompt_hints


class WriteLearningRecordTool(BaseTool):
    """Persist a structured learning record from the coach's teaching session."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="write_learning_record",
            description=(
                "Persist a structured learning record (diagnosis, theory_mastered, or "
                "annotation_exercise) to the learner's long-term learning store. "
                "Call AFTER: Phase0 diagnosis completes, each theory concept passes the "
                "readiness gate, and each practice task is evaluated + feedback given. "
                "Drives the progress dashboard and lets the next conversation resume. "
                "JSON schema: {\"type\":\"annotation_exercise\",\"task_id\":\"task1\","
                "\"knowledge_point\":\"...\",\"f1\":0.85,\"precision\":0.9,\"recall\":0.81,"
                "\"difficulty\":\"medium\",\"confidence\":0.9,\"source\":\"explicit\","
                "\"error_pattern\":null,\"readiness\":\"advance\","
                "\"teach_back_score\":\"3/3/2\",\"knowledge_points\":[\"...\"],"
                "\"session_summary\":\"...\"}. Types: diagnosis (teaching_mode required), "
                "theory_mastered (knowledge_point + readiness required), annotation_exercise "
                "(task_id required). Never call for preferences — use write_memory instead."
            ),
            parameters=[
                ToolParameter(
                    name="record",
                    type="string",
                    description=(
                        "JSON string of the learning record. See the schema in the "
                        "description. Must include a valid 'type'."
                    ),
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from deeptutor.services.learning_records import (
            LearningRecordStore,
            validate_record,
        )

        raw = kwargs.get("record")
        if raw is None:
            return ToolResult(content="Error: record is required.", success=False)
        if isinstance(raw, str):
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as exc:
                return ToolResult(
                    content=f"Error: record is not valid JSON — {exc}",
                    success=False,
                )
        elif isinstance(raw, dict):
            record = raw
        else:
            return ToolResult(
                content=f"Error: record must be a JSON object or string, got {type(raw).__name__}.",
                success=False,
            )

        error = validate_record(record)
        if error:
            return ToolResult(content=f"Error: {error}", success=False)

        try:
            persisted = await LearningRecordStore().append(record)
        except Exception as exc:
            return ToolResult(content=f"Error: failed to persist record — {exc}", success=False)

        try:
            from deeptutor.services.knowledge_graph import KnowledgeGraphStore

            KnowledgeGraphStore().incremental_update(persisted)
        except Exception:
            # graph is a derived index — failure must not break record persistence
            pass

        kind = persisted.get("type")
        return ToolResult(
            content=(
                f"Learning record saved (type={kind}, timestamp={persisted.get('timestamp', '?')}). "
                "Summary mirrored to memory for next-session resume."
            ),
            metadata={
                "type": kind,
                "timestamp": persisted.get("timestamp"),
                "task_id": persisted.get("task_id"),
                "knowledge_point": persisted.get("knowledge_point"),
                "readiness": persisted.get("readiness"),
                "f1": persisted.get("f1"),
            },
        )

    def get_prompt_hints(self, language: str = "en") -> Any:
        hints = load_prompt_hints(self.name, language=language)
        if hints.short_description:
            return hints
        return super().get_prompt_hints(language=language)
