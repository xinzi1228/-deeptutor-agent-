from deeptutor.api.routers.label_studio_gateway import _inject_realtime_bridge
from deeptutor.services.label_studio_gateway import LabelStudioAccessPolicy, LabelStudioProfileMap


def test_profile_map_uses_small_starter_assignment_then_explicit_assignments(tmp_path) -> None:
    mapping = LabelStudioProfileMap.load(tmp_path, "lp_1234567890abcdef12345678")
    assert mapping.assigned(["task1", "task2", "task3", "task4"]) == ["task1", "task2", "task3"]
    mapping.assigned_task_ids = ["task4", "task2", "task4"]
    mapping.save(tmp_path)
    restored = LabelStudioProfileMap.load(tmp_path, mapping.profile_id)
    assert restored.assigned(["task1"]) == ["task4", "task2"]


def test_realtime_bridge_only_injects_into_project_workbench_html() -> None:
    html = "<html><body><main>Label Studio</main></body></html>"
    injected = _inject_realtime_bridge(html, "projects/11/data")
    assert "data-deeptutor-label-studio-bridge" in injected
    assert "annotationCount" in injected
    assert "clientX" not in injected
    assert _inject_realtime_bridge(html, "user/login") == html
    assert _inject_realtime_bridge(injected, "projects/11/data") == injected


def _policy() -> LabelStudioAccessPolicy:
    return LabelStudioAccessPolicy(
        LabelStudioProfileMap(
            profile_id="lp_a", email_alias="a@example.invalid", project_id=11,
            task_map={"task-a": 101, "task-b": 102},
        )
    )


def test_policy_allows_only_mapped_project_and_tasks() -> None:
    policy = _policy()
    assert policy.allows("GET", "/projects/11/data", "task=101")
    assert policy.allows("POST", "/api/tasks/101/annotations")
    assert not policy.allows("GET", "/projects/12/data", "task=101")
    assert not policy.allows("GET", "/projects/11/data", "task=999")
    assert not policy.allows("GET", "/api/users")
    assert not policy.allows("GET", "/organization")


def test_policy_rejects_cross_profile_mutation_body() -> None:
    policy = _policy()
    assert policy.validate_mutation_body("api/tasks/101/annotations", b'{"task":101,"result":[]}')
    assert not policy.validate_mutation_body("api/tasks/101/annotations", b'{"task":999,"result":[]}')
    assert not policy.validate_mutation_body("api/tasks/101/annotations", b"not-json")


def test_annotation_id_routes_are_only_candidates_for_router_owner_check() -> None:
    policy = _policy()
    assert policy.allows("GET", "/api/annotations/501")
    assert policy.allows("PATCH", "/api/annotations/501")
    assert policy.allows("DELETE", "/api/annotations/501")
    assert not policy.allows("POST", "/api/annotations/501")
    assert not policy.allows("GET", "/api/annotations/not-a-number")
