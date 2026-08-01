"""V1 feature verification script."""
import asyncio, json, sys
from pathlib import Path

results = []

def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append((name, status, detail))
    print(f"[{status}] {name} {detail}")

# 1. Tool registration
from deeptutor.tools.builtin import BUILTIN_TOOL_NAMES
tools = ['annotation_check', 'get_annotation_task', 'competency_map', 'job_analysis']
reg = all(t in BUILTIN_TOOL_NAMES for t in tools)
check("Tool registration", reg, str(tools))

# 2. Competency map
from deeptutor.tools.competency_tool import CompetencyMapTool
cm = CompetencyMapTool()
r = asyncio.run(cm.execute(action='overview'))
n = r.metadata['total_nodes']
t = r.metadata['total_tasks']
s = r.metadata['total_skills']
check("Competency map", n >= 40, f"{n} nodes / {t} tasks / {s} skills")

# 3. Job analysis
from deeptutor.tools.job_analysis_tool import JobAnalysisTool
ja = JobAnalysisTool()
r = asyncio.run(ja.execute(section='trends'))
check("Job analysis", '2026' in r.content, "trends section")

# 4. Task bank
from deeptutor.tools.task_bank_tool import GetAnnotationTaskTool, _load_bank
bank = _load_bank()
has9 = len(bank) >= 9 and all(f'task{i}' in bank for i in range(1, 10))
types = set(t['type'] for t in bank.values())
diffs = set(t['difficulty'] for t in bank.values())
check("Task bank", has9, f"{len(bank)} tasks, types={types}, diffs={diffs}")

# 5. Annotation check
from deeptutor.tools.annotation_check import AnnotationCheckTool
ac = AnnotationCheckTool()
gt = json.dumps([{'x': 207, 'y': 140, 'w': 353, 'h': 273, 'label': 'car'}])
pred = json.dumps([{'x': 207, 'y': 140, 'w': 353, 'h': 273, 'label': 'car'}])
r = asyncio.run(ac.execute(predictions=pred, ground_truth=gt, task_type='bbox'))
check("Annotation check", '100%' in r.content, "perfect match F1=100%")

# 6. Knowledge base docs
kb_dir = Path('data/user/workspace/annotation_kb')
if kb_dir.exists():
    count = len(list(kb_dir.rglob('*.md')))
    check("Knowledge base", count >= 50, f"{count} markdown docs")
else:
    check("Knowledge base", False, "directory not found")

# 7. Task format test
tbt = GetAnnotationTaskTool()
r = asyncio.run(tbt.execute(task_id='task1'))
check("Task1 format", 'car' in r.content and 'easy' in r.content, "bbox easy task")
r = asyncio.run(tbt.execute(task_id='task5'))
check("Task5 format", 'classification' in str(r.content), "classification task")
r = asyncio.run(tbt.execute(task_id='task8'))
check("Task8 format", 'hard' in r.content, "hard bbox task")

# Summary
print("\n" + "=" * 50)
passed = sum(1 for _, s, _ in results if s == "PASS")
failed = len(results) - passed
print(f"Total: {len(results)} tests, {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
