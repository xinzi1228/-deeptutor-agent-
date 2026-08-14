from pathlib import Path
from types import SimpleNamespace

from deeptutor.services.student_dashboard.cache import StudentDashboardCache
from deeptutor.services.student_dashboard.service import StudentDashboardService


class FakeStore:
    def __init__(self, file: Path) -> None:
        self.file = file

    def list_records(self):
        return [{"type": "annotation_exercise", "task_id": "task-a"}]


class FakeStats:
    def __init__(self) -> None:
        self.overview_calls = 0

    def overview(self):
        self.overview_calls += 1
        return {"total_tasks_completed": self.overview_calls}

    def foresight_stats(self):
        return {"total": 0, "verified": 0, "hits": 0, "hit_rate": None, "open": 0}


class FakeWorkspace:
    def __init__(self) -> None:
        self.version = "assets-v1"

    def asset_versions(self):
        return {"task_bank": {"sha256": self.version, "updated_at": None}}


class FakeTaskStore:
    def __init__(self) -> None:
        self.version = 1

    def get(self):
        return SimpleNamespace(version=self.version, model_dump=lambda **_: {"version": self.version})


def _service(tmp_path: Path, *, profile_id: str = "profile-a"):
    records = tmp_path / profile_id / "learning" / "records.jsonl"
    records.parent.mkdir(parents=True)
    records.write_text('{"type":"annotation_exercise"}\n', encoding="utf-8")
    stats = FakeStats()
    workspace = FakeWorkspace()
    task_store = FakeTaskStore()
    service = StudentDashboardService(
        profile_id=profile_id,
        profile_root=tmp_path / profile_id,
        store=FakeStore(records),
        stats=stats,
        workspace=workspace,
        task_store=task_store,
        cache=StudentDashboardCache(),
        report_builder=lambda records: {"summary": {"completed_count": len(records)}},
    )
    return service, stats, workspace, task_store, records


def test_home_projection_is_cached_until_learning_truth_changes(tmp_path: Path):
    service, stats, _, _, records = _service(tmp_path)

    first = service.home()
    second = service.home()
    assert stats.overview_calls == 1
    assert first == second

    records.write_text(records.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
    third = service.home()
    assert stats.overview_calls == 2
    assert third["version"]["learning_data_version"] != first["version"]["learning_data_version"]


def test_task_and_content_versions_invalidate_only_the_matching_projection(tmp_path: Path):
    service, stats, workspace, task_store, _ = _service(tmp_path)
    first = service.home()

    task_store.version = 2
    task_changed = service.home()
    assert stats.overview_calls == 2
    assert task_changed["version"]["task_version"] == 2

    workspace.version = "assets-v2"
    content_changed = service.home()
    assert stats.overview_calls == 3
    assert content_changed["version"]["learning_data_version"] != task_changed["version"]["learning_data_version"]
    assert first["version"]["profile_id"] == "profile-a"


def test_cache_never_crosses_learning_profiles(tmp_path: Path):
    shared_cache = StudentDashboardCache()
    service_a, stats_a, _, _, _ = _service(tmp_path, profile_id="profile-a")
    service_b, stats_b, _, _, _ = _service(tmp_path, profile_id="profile-b")
    service_a.cache = shared_cache
    service_b.cache = shared_cache

    assert service_a.home()["version"]["profile_id"] == "profile-a"
    assert service_b.home()["version"]["profile_id"] == "profile-b"
    assert stats_a.overview_calls == 1
    assert stats_b.overview_calls == 1
