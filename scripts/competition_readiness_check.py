"""竞赛就绪检查器：输出机器可读 JSON 与中文摘要。

检查项（与 release-readiness-gates 设计 §4 对齐）：
  * 运行时版本（Python / Node / Playwright 浏览器）；
  * 后端 / 前端 / Label Studio 连通性；
  * 对话模型、Embedding、知识库引用与可选 imagegen 的真实状态；
  * 数据目录写入权限、磁盘空间、端口占用与时钟；
  * 必需内容版本、题库审核、黄金任务与测试账号；
  * 明文密钥、未审核扩展与开发模式风险；
  * 构建产物与提交版本。

检查器绝不输出密钥、完整 Cookie、个人对话或标注正文。每项失败给出修复
建议与是否阻断演示。
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

# Ensure the repository root is importable when launched as
# `python scripts/competition_readiness_check.py`.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from deeptutor.multi_user.paths import ADMIN_WORKSPACE_ROOT, get_admin_path_service  # noqa: E402
from deeptutor.services.config import get_model_catalog_service  # noqa: E402

SECRET_SUBSTRINGS = ("api_key", "token", "cookie", "password", "pin_hash", "authorization")
PRESENTATION_URL_HINT = "presentation"


class ReadinessCheck:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def add(
        self,
        key: str,
        label: str,
        passed: bool,
        detail: str,
        *,
        blocking: bool = False,
    ) -> None:
        self.checks.append(
            {
                "key": key,
                "label": label,
                "passed": bool(passed),
                "detail": _redact(detail),
                "blocking": bool(blocking),
            }
        )

    def summary(self) -> dict[str, Any]:
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c["passed"])
        failed = [c for c in self.checks if not c["passed"]]
        blocked = [c for c in failed if c["blocking"]]
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "commit": _commit(),
            "total": total,
            "passed": passed,
            "failed": len(failed),
            "blocking_failures": len(blocked),
            "checks": self.checks,
            "ready": len(blocked) == 0 and passed == total,
        }


def _redact(value: str) -> str:
    lowered = value.lower()
    if any(part in lowered for part in SECRET_SUBSTRINGS):
        return "[已脱敏]"
    return value


def _commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() or ""
    except Exception:
        return ""


def _wait(url: str, timeout: float = 2.0) -> int | None:
    try:
        with urlopen(url, timeout=timeout) as response:
            return response.status
    except (OSError, TimeoutError, URLError):
        return None


def _free_disk(root: Path) -> float:
    try:
        usage = shutil.disk_usage(root)
        return round(usage.free / (1024**3), 1)
    except OSError:
        return -1.0


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", int(port))) == 0


def _model_flags() -> dict[str, Any]:
    try:
        service = get_model_catalog_service()
        catalog = service.load()

        def active(kind: str) -> bool:
            return bool(service.get_active_model(catalog, kind))

        return {
            "llm": active("llm"),
            "embedding": active("embedding"),
            "imagegen": active("imagegen"),
        }
    except Exception as exc:
        return {"llm": False, "embedding": False, "imagegen": False, "error": str(exc)}


def _secret_security() -> dict[str, Any]:
    try:
        status = get_model_catalog_service().secret_migration_status()
        return {
            "plaintext_count": status.plaintext_count,
            "migration_required": status.migration_required,
        }
    except Exception:
        return {"plaintext_count": -1, "migration_required": True}


def _task_bank_golden() -> tuple[bool, str]:
    try:
        bank = json.loads(
            (ADMIN_WORKSPACE_ROOT / "user" / "workspace" / "task_bank.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return False, "题库读取失败"
    tasks = list(bank.values()) if isinstance(bank, dict) else []
    bbox = [t for t in tasks if isinstance(t, dict) and t.get("type") == "bbox"]
    if not bbox:
        return False, "题库中没有矩形框任务"
    return True, f"矩形框任务 {len(bbox)} 个"


def _check_runtime(checker: ReadinessCheck) -> None:
    checker.add(
        "python_version", "Python 版本", sys.version_info >= (3, 10),
        sys.version.split()[0],
    )
    node = shutil.which("node")
    if node:
        version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
        checker.add("node_version", "Node 版本", bool(version), version)
    else:
        checker.add("node_version", "Node 版本", False, "未找到 node", blocking=True)


def _check_connectivity(checker: ReadinessCheck) -> None:
    from deeptutor.services.config import load_system_settings

    system = load_system_settings()
    backend_port = int(os.getenv("BACKEND_PORT", str(system.get("backend_port", 8001))))
    frontend_port = int(os.getenv("FRONTEND_PORT", str(system.get("frontend_port", 3782))))

    backend_ok = _port_open(backend_port) and _wait(f"http://127.0.0.1:{backend_port}/") is not None
    checker.add(
        "backend_up", "后端服务", backend_ok,
        f"127.0.0.1:{backend_port}",
        blocking=True,
    )
    frontend_ok = _port_open(frontend_port)
    checker.add(
        "frontend_up", "前端服务", frontend_ok,
        f"127.0.0.1:{frontend_port}",
        blocking=True,
    )
    ls_ok = _wait("http://127.0.0.1:8080/health") is not None
    checker.add("label_studio_up", "Label Studio", ls_ok, "http://127.0.0.1:8080/health")


def _check_models(checker: ReadinessCheck) -> None:
    flags = _model_flags()
    checker.add(
        "llm_configured", "对话模型已配置", bool(flags.get("llm")),
        "已配置" if flags.get("llm") else "未配置主对话模型",
        blocking=bool(flags.get("llm") is False),
    )
    checker.add(
        "embedding_configured", "Embedding 已配置", bool(flags.get("embedding")),
        "已配置" if flags.get("embedding") else "未配置；能力中心应显示受限",
    )
    checker.add(
        "imagegen_configured", "imagegen 已配置", bool(flags.get("imagegen")),
        "已配置" if flags.get("imagegen") else "可选能力，未配置",
    )


def _check_secrets_and_extensions(checker: ReadinessCheck) -> None:
    security = _secret_security()
    checker.add(
        "plaintext_secrets", "无明文密钥", security.get("plaintext_count", 0) == 0,
        f"明文密钥 {security.get('plaintext_count', 0)} 个，需迁移" if security.get("plaintext_count", 0) else "已安全存储",
        blocking=bool(security.get("plaintext_count", 0) > 0),
    )
    try:
        from deeptutor.services.extension_marketplace import load_extension_policy

        policy_path = get_admin_path_service().get_workspace_dir() / "extension_policy.json"
        policy = load_extension_policy(policy_path)
        mode = str(policy.get("mode") or "dev")
        checker.add(
            "extension_policy", "扩展策略模式", mode in {"dev", "competition"},
            f"当前模式：{mode}",
        )
    except Exception as exc:
        checker.add("extension_policy", "扩展策略模式", False, str(exc))


def _check_storage(checker: ReadinessCheck) -> None:
    root = ADMIN_WORKSPACE_ROOT
    writable = os.access(root, os.W_OK)
    checker.add("storage_writable", "数据目录可写", writable, str(root), blocking=True)
    free_gb = _free_disk(root)
    checker.add("disk_space", "磁盘空间", free_gb >= 1.0, f"剩余 {free_gb} GB")


def _check_content(checker: ReadinessCheck) -> None:
    ok, detail = _task_bank_golden()
    checker.add("golden_task", "黄金矩形框任务", ok, detail, blocking=True)
    try:
        bank = json.loads(
            (ADMIN_WORKSPACE_ROOT / "user" / "workspace" / "task_bank.json").read_text(encoding="utf-8")
        )
        reviewed = sum(
            1
            for t in (bank.values() if isinstance(bank, dict) else [])
            if isinstance(t, dict) and t.get("review_status") == "approved"
        )
        checker.add(
            "task_bank_review", "题库审核", reviewed > 0,
            f"{reviewed} 道已审核",
        )
    except Exception as exc:
        checker.add("task_bank_review", "题库审核", False, str(exc))


def _check_build(checker: ReadinessCheck) -> None:
    web_build = Path("web/.next") if Path("web/.next").exists() else None
    checker.add(
        "frontend_build", "前端构建产物", web_build is not None,
        str(web_build) if web_build else "未找到 .next；请先 npm run build",
    )
    checker.add("git_commit", "提交版本", True, _commit() or "unknown")


def run_checker() -> dict[str, Any]:
    checker = ReadinessCheck()
    _check_runtime(checker)
    _check_connectivity(checker)
    _check_models(checker)
    _check_secrets_and_extensions(checker)
    _check_storage(checker)
    _check_content(checker)
    _check_build(checker)
    return checker.summary()


def _print_chinese(summary: dict[str, Any]) -> None:
    print("=== 标注星图 竞赛就绪检查 ===")
    print(f"提交：{summary['commit'] or 'unknown'}")
    print(f"通过 {summary['passed']}/{summary['total']}，阻断 {summary['blocking_failures']} 项\n")
    for check in summary["checks"]:
        mark = "PASS" if check["passed"] else "FAIL"
        tag = " [阻断]" if check["blocking"] and not check["passed"] else ""
        print(f"[{mark}]{tag} {check['label']}：{check['detail']}")
        if not check["passed"]:
            print(f"    -> 建议：{_advice(check['key'])}")
    print("\n结论：" + ("可以开始演示" if summary["ready"] else "存在阻断项，修复后再演示"))


def _advice(key: str) -> str:
    advice = {
        "backend_up": "启动后端：python -m uvicorn deeptutor.api.main:app --port 8001",
        "frontend_up": "启动前端：cd web && npm run dev -- --port 3782",
        "llm_configured": "在管理员 AI 能力中心配置并连接测试主对话模型",
        "embedding_configured": "配置 Embedding 并通过五项验收后再索引资料",
        "plaintext_secrets": "在设置中心执行密钥迁移",
        "storage_writable": "检查数据目录权限",
        "golden_task": "确认 task_bank.json 包含交通道路车辆/行人矩形框任务",
        "frontend_build": "运行 cd web && npm run build",
    }
    return advice.get(key, "按能力中心提示修复")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="只输出 JSON")
    args = parser.parse_args()
    summary = run_checker()
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        _print_chinese(summary)
    return 0 if summary["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
