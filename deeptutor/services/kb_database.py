"""Runtime access to data_annotation_kb.db knowledge base."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent.parent.parent / "data" / "data_annotation_kb.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_knowledge_points(modality_id: int | None = None) -> list[dict[str, Any]]:
    """Get knowledge points, optionally filtered by modality."""
    conn = get_conn()
    sql = """
        SELECT kp.*, am.modality_name, dl.level_name
        FROM knowledge_point kp
        JOIN annotation_modality am ON kp.modality_id = am.id
        JOIN difficulty_level dl ON kp.difficulty_id = dl.id
        WHERE kp.is_deleted = 0
    """
    params: tuple = ()
    if modality_id is not None:
        sql += " AND kp.modality_id = ?"
        params = (modality_id,)
    sql += " ORDER BY kp.modality_id, dl.sort, kp.sort"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_quizzes(modality_id: int | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Get quiz questions with options."""
    conn = get_conn()
    sql = """
        SELECT q.*, am.modality_name, kp.point_name
        FROM quiz q
        JOIN knowledge_point kp ON q.point_id = kp.id
        JOIN annotation_modality am ON kp.modality_id = am.id
        WHERE q.is_deleted = 0
    """
    params: tuple = ()
    if modality_id is not None:
        sql += " AND kp.modality_id = ?"
        params = (modality_id,)
    sql += " ORDER BY q.sort LIMIT ?"
    params = params + (limit,)

    quizzes = conn.execute(sql, params).fetchall()
    result = []
    for q in quizzes:
        d = dict(q)
        options = conn.execute(
            "SELECT * FROM quiz_option WHERE quiz_id = ? ORDER BY sort", (q["id"],)
        ).fetchall()
        d["options"] = [dict(o) for o in options]
        result.append(d)
    conn.close()
    return result


def get_common_errors(point_id: int | None = None) -> list[dict[str, Any]]:
    """Get common annotation errors."""
    conn = get_conn()
    sql = """
        SELECT ce.*, kp.point_name
        FROM common_error ce
        JOIN knowledge_point kp ON ce.point_id = kp.id
        WHERE ce.is_deleted = 0
    """
    params: tuple = ()
    if point_id is not None:
        sql += " AND ce.point_id = ?"
        params = (point_id,)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_glossary() -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM glossary ORDER BY sort"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_learning_paths(modality_id: int | None = None) -> list[dict[str, Any]]:
    conn = get_conn()
    sql = """
        SELECT lp.*, am.modality_name
        FROM learning_path lp
        JOIN annotation_modality am ON lp.modality_id = am.id
        WHERE lp.is_deleted = 0
    """
    params: tuple = ()
    if modality_id is not None:
        sql += " AND lp.modality_id = ?"
        params = (modality_id,)
    sql += " ORDER BY lp.sort"
    paths = conn.execute(sql, params).fetchall()
    result = []
    for p in paths:
        d = dict(p)
        steps = conn.execute(
            """SELECT lps.step_order, kp.point_name, kp.learning_requirement
               FROM learning_path_step lps
               JOIN knowledge_point kp ON lps.point_id = kp.id
               WHERE lps.path_id = ? ORDER BY lps.step_order""",
            (p["id"],),
        ).fetchall()
        d["steps"] = [dict(s) for s in steps]
        result.append(d)
    conn.close()
    return result


def get_best_practices(modality_id: int | None = None) -> list[dict[str, Any]]:
    conn = get_conn()
    sql = "SELECT * FROM best_practice WHERE 1=1"
    params: tuple = ()
    if modality_id is not None:
        sql += " AND modality_id = ?"
        params = (modality_id,)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_knowledge(query: str) -> list[dict[str, Any]]:
    """Full-text-like search across knowledge points and glossary."""
    conn = get_conn()
    like = f"%{query}%"
    kps = conn.execute(
        """SELECT kp.point_name, kp.learning_requirement, am.modality_name
           FROM knowledge_point kp
           JOIN annotation_modality am ON kp.modality_id = am.id
           WHERE kp.is_deleted = 0
           AND (kp.point_name LIKE ? OR kp.learning_requirement LIKE ?)
           LIMIT 20""",
        (like, like),
    ).fetchall()
    glossary = conn.execute(
        "SELECT term, definition FROM glossary WHERE term LIKE ? OR definition LIKE ? LIMIT 10",
        (like, like),
    ).fetchall()
    conn.close()
    return {
        "knowledge_points": [dict(r) for r in kps],
        "glossary": [dict(r) for r in glossary],
    }
