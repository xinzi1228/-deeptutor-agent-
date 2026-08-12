from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "label_studio_capability_probe.py"
SPEC = importlib.util.spec_from_file_location("label_studio_capability_probe", SCRIPT)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = probe
SPEC.loader.exec_module(probe)


def test_redact_recursively_removes_secrets_and_emails():
    secret = "test-token-should-never-leak"
    source = {
        "token": secret,
        "nested": {
            "Authorization": f"Token {secret}",
            "message": f"login student@example.com password={secret}",
        },
        "rows": [{"cookie": f"sessionid={secret}"}],
    }

    rendered = json.dumps(probe.redact(source), ensure_ascii=False)

    assert secret not in rendered
    assert "student@example.com" not in rendered
    assert rendered.count("[REDACTED]") >= 3
    assert "[REDACTED_EMAIL]" in rendered


def test_classify_project_isolation_rejects_list_discovery():
    result = probe.classify_project_isolation(
        owner_project_id=7,
        peer_project_list_status=200,
        peer_projects={"results": [{"id": 7}]},
        peer_direct_status=404,
    )
    assert result["status"] == "unsupported"
    assert result["evidence"]["owner_project_visible"] is True


def test_classify_project_isolation_rejects_direct_access():
    result = probe.classify_project_isolation(7, 200, [], 200)
    assert result["status"] == "unsupported"
    assert result["evidence"]["direct_access_status"] == 200


def test_classify_project_isolation_accepts_hidden_and_forbidden():
    result = probe.classify_project_isolation(7, 200, [], 403)
    assert result["status"] == "supported"


def test_report_recommends_gateway_when_native_isolation_fails():
    report = probe._report(
        "http://127.0.0.1:18080",
        {"release": "1.23.0"},
        [probe.check("project_isolation", "unsupported", "leak")],
        live=True,
    )
    assert report["decision"]["strategy"] == "per_profile_project_with_same_origin_gateway"
    assert report["target"]["origin"] == "http://127.0.0.1:18080"


def test_no_redirect_handler_preserves_redirect_as_evidence():
    handler = probe._NoRedirect()
    assert callable(handler.http_error_302)


@pytest.mark.integration
def test_live_probe_against_explicit_isolated_instance():
    if os.getenv("LABEL_STUDIO_PROBE_LIVE") != "1":
        pytest.skip("set LABEL_STUDIO_PROBE_LIVE=1 for isolated local integration")
    report = probe.run_probe(
        os.environ["LABEL_STUDIO_PROBE_URL"],
        os.environ["LABEL_STUDIO_PROBE_API_TOKEN"],
        live=True,
    )
    assert report["live"] is True
    assert report["target"]["version"]
    assert all("test-token-should-never-leak" not in json.dumps(item) for item in report["checks"])
