"""Run a disposable end-to-end check of the professional annotation gateway.

The check starts a brand-new Label Studio in a temporary directory. It never
opens or mutates the project's regular ``data/label-studio`` database.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterator
from urllib.error import URLError
from urllib.request import urlopen


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_ready(url: str, process: subprocess.Popen[bytes], timeout: float = 480) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"隔离 Label Studio 提前退出，退出码 {process.returncode}")
        try:
            with urlopen(f"{url}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, TimeoutError, URLError):
            pass
        time.sleep(0.5)
    raise RuntimeError("等待隔离 Label Studio 启动超时")


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


@contextmanager
def _isolated_label_studio(home: Path) -> Iterator[str]:
    executable = shutil.which("label-studio")
    if not executable:
        raise RuntimeError("未安装 label-studio，无法运行专业模式端到端验收")
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    data_dir = home / "data" / "label-studio"
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = home / "label-studio-e2e.log"
    token = secrets.token_hex(20)
    password = "E2e!" + secrets.token_urlsafe(18)
    common = [
        "--no-browser",
        "--skip-long-migrations",
        "--enable-legacy-api-token",
        "--data-dir",
        str(data_dir),
        "--username",
        "gateway-e2e@localhost",
        "--password",
        password,
        "--user-token",
        token,
    ]
    environment = os.environ.copy()
    environment.update(
        {
            "LATEST_VERSION_CHECK": "false",
            "COLLECT_ANALYTICS": "false",
            "SENTRY_DSN": "",
        }
    )
    command = [executable, "start", "--init", *common, "--port", str(port)]
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            command,
            cwd=home,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            _wait_ready(base_url, process)
            yield base_url
        finally:
            _terminate_process_tree(process)


def _assert_status(response: Any, expected: int, label: str) -> dict[str, Any]:
    if response.status_code != expected:
        raise AssertionError(
            f"{label}：期望 HTTP {expected}，实际 {response.status_code}，"
            f"响应 {response.text[:300]}"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise AssertionError(f"{label}：响应不是 JSON 对象")
    return payload


def run_gateway_e2e(source_root: Path) -> dict[str, Any]:
    """Exercise SSO bridge, sync, profile isolation and teacher read-only mode."""
    source_text = str(source_root)
    if source_text not in sys.path:
        sys.path.insert(0, source_text)
    # Windows can keep the just-closed SQLite handle alive for a short time.
    # The process tree is always stopped above; cleanup errors must not hide a
    # completed security result from CI or the operator.
    with tempfile.TemporaryDirectory(
        prefix="deeptutor-ls-gateway-e2e-", ignore_cleanup_errors=True
    ) as raw_home:
        home = Path(raw_home)
        workspace = home / "data" / "user" / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / "data" / "user" / "workspace" / "task_bank.json", workspace / "task_bank.json")

        previous = {
            key: os.environ.get(key)
            for key in ("DEEPTUTOR_HOME", "LABEL_STUDIO_URL", "LABEL_STUDIO_LOCAL_DB", "LABEL_STUDIO_API_TOKEN")
        }
        os.environ["DEEPTUTOR_HOME"] = str(home)
        os.environ.pop("LABEL_STUDIO_API_TOKEN", None)
        try:
            with _isolated_label_studio(home) as base_url:
                os.environ["LABEL_STUDIO_URL"] = base_url
                os.environ["LABEL_STUDIO_LOCAL_DB"] = str(
                    home / "data" / "label-studio" / "label_studio.sqlite3"
                )

                from fastapi import Depends, FastAPI
                from fastapi.testclient import TestClient

                from deeptutor.api.routers import (
                    annotation,
                    label_studio_gateway,
                    learning_profiles,
                )
                from deeptutor.api.routers.auth import require_auth
                from deeptutor.services.label_studio_gateway.session_bridge import (
                    LabelStudioSessionBridge,
                )

                LabelStudioSessionBridge._cookies.clear()
                app = FastAPI()
                app.include_router(
                    learning_profiles.router, prefix="/api/v1/learning-profiles"
                )
                app.include_router(
                    annotation.router,
                    prefix="/api/v1/annotation",
                    dependencies=[Depends(require_auth)],
                )
                app.include_router(
                    label_studio_gateway.router,
                    prefix="/api/v1/label-studio",
                    dependencies=[Depends(require_auth)],
                )

                checks: dict[str, Any] = {}
                with TestClient(app) as client:
                    first = _assert_status(
                        client.post(
                            "/api/v1/learning-profiles",
                            json={"name": "端到端学生甲", "pin": "1357"},
                        ),
                        201,
                        "创建档案甲",
                    )
                    profile_a = str(first["id"])
                    _assert_status(
                        client.post(
                            f"/api/v1/learning-profiles/{profile_a}/unlock",
                            json={"pin": "1357"},
                        ),
                        200,
                        "解锁档案甲",
                    )
                    status_a = _assert_status(
                        client.get("/api/v1/label-studio/status"), 200, "专业模式状态"
                    )
                    if status_a.get("credential_mode") != "local_auto":
                        raise AssertionError("隔离实例没有使用本机自动凭据")
                    prepared_a = _assert_status(
                        client.post("/api/v1/label-studio/prepare/task1"),
                        200,
                        "准备档案甲任务",
                    )
                    workbench = client.get(prepared_a["workbench_url"])
                    if workbench.status_code != 200 or "user/login" in str(workbench.url):
                        raise AssertionError("专业工作台没有通过隐藏会话直接打开")
                    checks["single_sign_on"] = "passed"

                    annotation_payload = {
                        "result": [
                            {
                                "from_name": "label",
                                "to_name": "image",
                                "type": "rectanglelabels",
                                "value": {
                                    "x": 20,
                                    "y": 20,
                                    "width": 30,
                                    "height": 30,
                                    "rectanglelabels": ["car"],
                                },
                            }
                        ],
                        "was_cancelled": False,
                        "ground_truth": False,
                        "task": prepared_a["ls_task_id"],
                    }
                    submitted = client.post(
                        f"/api/v1/label-studio/proxy/api/tasks/{prepared_a['ls_task_id']}/annotations/",
                        json=annotation_payload,
                    )
                    if submitted.status_code not in {200, 201}:
                        raise AssertionError(
                            f"专业标注提交失败：HTTP {submitted.status_code} {submitted.text[:300]}"
                        )
                    synced = _assert_status(
                        client.post("/api/v1/label-studio/sync/task1"),
                        200,
                        "同步专业标注",
                    )
                    if not synced.get("synced"):
                        raise AssertionError("专业标注没有同步进学习档案")
                    checks["annotation_sync"] = "passed"

                    _assert_status(
                        client.post("/api/v1/learning-profiles/lock"), 200, "锁定档案甲"
                    )
                    second = _assert_status(
                        client.post(
                            "/api/v1/learning-profiles",
                            json={"name": "端到端学生乙", "pin": "2468"},
                        ),
                        201,
                        "创建档案乙",
                    )
                    profile_b = str(second["id"])
                    _assert_status(
                        client.post(
                            f"/api/v1/learning-profiles/{profile_b}/unlock",
                            json={"pin": "2468"},
                        ),
                        200,
                        "解锁档案乙",
                    )
                    prepared_b = _assert_status(
                        client.post("/api/v1/label-studio/prepare/task2"),
                        200,
                        "准备档案乙任务",
                    )
                    cross_project = client.get(prepared_a["workbench_url"])
                    cross_task = client.get(
                        f"/api/v1/label-studio/proxy/api/tasks/{prepared_a['ls_task_id']}"
                    )
                    if cross_project.status_code != 403 or cross_task.status_code != 403:
                        raise AssertionError("档案乙能够访问档案甲的专业标注资源")
                    if prepared_a["project_id"] == prepared_b["project_id"]:
                        raise AssertionError("两个档案错误复用了同一 Label Studio 项目")
                    checks["cross_profile_isolation"] = "passed"

                    _assert_status(
                        client.post(
                            f"/api/v1/learning-profiles/{profile_b}/teacher-view"
                        ),
                        200,
                        "进入教师只读视角",
                    )
                    teacher_write = client.post(
                        "/api/v1/annotation/activity",
                        json={"task_id": "task2", "stage": "teacher-write-test"},
                    )
                    teacher_proxy_write = client.post(
                        f"/api/v1/label-studio/proxy/api/tasks/{prepared_b['ls_task_id']}/annotations/",
                        json=annotation_payload | {"task": prepared_b["ls_task_id"]},
                    )
                    if teacher_write.status_code != 403 or teacher_proxy_write.status_code != 403:
                        raise AssertionError("教师只读视角仍可写入学生标注数据")
                    checks["teacher_read_only"] = "passed"

                return {
                    "schema_version": 1,
                    "isolated": True,
                    "formal_data_touched": False,
                    "label_studio_origin": "loopback-disposable",
                    "profiles_checked": 2,
                    "checks": checks,
                    "result": "passed",
                }
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="隔离运行标注星图专业模式端到端验收")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="包含 task_bank.json 的项目根目录",
    )
    parser.add_argument("--output", type=Path, help="可选的脱敏 JSON 验收结果")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    report = run_gateway_e2e(args.source_root.resolve())
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
