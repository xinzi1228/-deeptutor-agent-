#!/usr/bin/env python3
"""Import data_annotation_kb.db into competency_tree.json and task_bank.json."""
import sqlite3, json, sys

DB_PATH = "data/data_annotation_kb.db"
TREE_PATH = "data/user/workspace/competency_tree.json"
BANK_PATH = "data/user/workspace/task_bank.json"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# ===== 1. Enrich competency_tree.json =====
tree = json.loads(open(TREE_PATH, "r", encoding="utf-8").read())

mod_map = {
    1: ("task-group-kb-1", "图像标注进阶(知识库)", "从知识库导入的图像标注知识点"),
    2: ("task-group-kb-2", "音频标注进阶(知识库)", "从知识库导入的音频标注知识点"),
    3: ("task-group-kb-3", "视频标注进阶(知识库)", "从知识库导入的视频标注知识点"),
    5: ("task-group-kb-4", "文本标注进阶(知识库)", "从知识库导入的文本标注知识点"),
}

kps_added = 0
for mod_id, (gid, gname, gdesc) in mod_map.items():
    kps = conn.execute("""
        SELECT kp.*, dl.level_name FROM knowledge_point kp
        JOIN difficulty_level dl ON kp.difficulty_id = dl.id
        WHERE kp.modality_id = ? AND kp.is_deleted = 0 ORDER BY difficulty_id, sort
    """, (mod_id,)).fetchall()
    if not kps:
        continue

    group = {"id": gid, "name": gname, "level": 2, "description": gdesc, "children": []}
    seen = set()

    for kp in kps:
        diff = kp["level_name"]
        diff_id = f"{gid}-{diff}"
        if diff_id not in seen:
            seen.add(diff_id)
            group["children"].append({
                "id": diff_id,
                "name": f"{diff}知识点",
                "level": 3,
                "description": f"{gname}的{diff}内容",
                "skills": [],
            })

        for child in group["children"]:
            if child["id"] == diff_id:
                sid = f"skill-kb-{mod_id}-{kp['id']}"
                if not any(s.get("id") == sid for s in child["skills"]):
                    child["skills"].append({
                        "id": sid,
                        "name": kp["point_name"],
                        "level": 4,
                        "description": (kp["learning_requirement"] or "")[:80],
                        "source": "data_annotation_kb.db",
                    })
                    kps_added += 1

    tree["tree"]["children"].append(group)

with open(TREE_PATH, "w", encoding="utf-8") as f:
    json.dump(tree, f, ensure_ascii=False, indent=2)
print(f"competency_tree: added 4 groups, {kps_added} skills")

# ===== 2. Add quiz tasks to task_bank.json =====
bank = json.loads(open(BANK_PATH, "r", encoding="utf-8").read())

quizzes = conn.execute("""
    SELECT q.*, kp.modality_id, kp.point_name FROM quiz q
    JOIN knowledge_point kp ON q.point_id = kp.id
    WHERE q.is_deleted = 0 ORDER BY q.id
""").fetchall()

modal_map = {1: "image", 2: "audio", 3: "video", 5: "text"}
highest_task = max(int(k.replace("task", "")) for k in bank.keys())
task_idx = highest_task + 1
quiz_added = 0

for q in quizzes:
    options = conn.execute(
        "SELECT * FROM quiz_option WHERE quiz_id = ? ORDER BY sort", (q["id"],)
    ).fetchall()
    if len(options) < 2:
        continue

    modal = modal_map.get(q["modality_id"], "image")
    correct_idx = next((i for i, o in enumerate(options) if o["is_correct"]), 0)
    letters = [chr(65 + i) for i in range(len(options))]
    correct_label = letters[correct_idx] if correct_idx < len(letters) else "A"

    tid = f"task{task_idx}"
    task_idx += 1
    quiz_added += 1

    bank[tid] = {
        "title": q["question_text"][:25],
        "type": "classification",
        "modal": modal,
        "difficulty": "easy",
        "object_count": 1,
        "text": q["question_text"],
        "labels": letters,
        "instruction": q["question_text"],
        "ground_truth": {"label": correct_label},
        "knowledge_points": [q["point_name"] or "标注基础"],
        "explanation": q["explanation"] or "",
        "items": [
            {"id": letters[i], "text": f"{letters[i]}. {options[i]['option_text']}"}
            for i in range(len(options))
        ],
        "source": "data_annotation_kb.db",
        "next_task": (
            f"task{task_idx}" if quiz_added < len(quizzes) else "task1"
        ),
    }

with open(BANK_PATH, "w", encoding="utf-8") as f:
    json.dump(bank, f, ensure_ascii=False, indent=2)
print(f"task_bank: added {quiz_added} quiz tasks, total {len(bank)} tasks")

conn.close()
print("Done")
