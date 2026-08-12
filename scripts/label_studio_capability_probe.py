"""Label Studio 1.23 capability probe with redacted evidence output.

The default mode is read-only. ``--live`` creates disposable projects, tasks,
users and annotations in an explicitly isolated Label Studio instance. Never
point live mode at the production data directory.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import re
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, HTTPCookieProcessor, Request, build_opener


SECRET_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "password",
    "token",
    "api_token",
    "csrfmiddlewaretoken",
}
SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)(token|password|authorization|cookie)=[^\s,;]+"),
    re.compile(r"(?i)\b(token|bearer)\s+[a-z0-9._~-]+"),
)


def redact(value: Any) -> Any:
    """Recursively remove credentials, cookies, e-mails and volatile HTML."""
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if str(key).lower() in SECRET_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"[\w.+-]+@[\w.-]+", "[REDACTED_EMAIL]", value)
        for pattern in SECRET_VALUE_PATTERNS:
            value = pattern.sub("[REDACTED]", value)
        return value[:1000]
    return value


@dataclass(slots=True)
class HttpResult:
    status: int
    body: Any
    headers: dict[str, str]
    url: str


class HttpClient:
    """Small stdlib HTTP client supporting API tokens and browser sessions."""

    def __init__(self, base_url: str, api_token: str = "", *, cookies: bool = False):
        self.base_url = base_url.rstrip("/") + "/"
        self.api_token = api_token
        self.jar = http.cookiejar.CookieJar() if cookies else None
        handlers = [HTTPCookieProcessor(self.jar)] if self.jar is not None else []
        self.opener = build_opener(*handlers)

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any | None = None,
        form: dict[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
        follow_redirects: bool = True,
    ) -> HttpResult:
        url = urljoin(self.base_url, path.lstrip("/"))
        headers = {"Accept": "application/json, text/html;q=0.8"}
        if self.api_token:
            headers["Authorization"] = f"Token {self.api_token}"
        if extra_headers:
            headers.update(extra_headers)
        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif form is not None:
            data = urlencode(form).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = Request(url, data=data, headers=headers, method=method.upper())
        if follow_redirects:
            opener = self.opener
        else:
            handlers = [HTTPCookieProcessor(self.jar)] if self.jar is not None else []
            opener = build_opener(*handlers, _NoRedirect())
        try:
            response = opener.open(request, timeout=15)
            raw = response.read().decode("utf-8", errors="replace")
            return HttpResult(
                status=response.status,
                body=_decode_body(raw, response.headers.get("Content-Type", "")),
                headers={key.lower(): value for key, value in response.headers.items()},
                url=response.geturl(),
            )
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            return HttpResult(
                status=exc.code,
                body=_decode_body(raw, exc.headers.get("Content-Type", "")),
                headers={key.lower(): value for key, value in exc.headers.items()},
                url=exc.geturl(),
            )
        except URLError as exc:
            return HttpResult(status=0, body={"error": str(exc.reason)}, headers={}, url=url)

    def csrf_token(self) -> str:
        if self.jar is None:
            return ""
        for cookie in self.jar:
            if cookie.name == "csrftoken":
                return cookie.value
        return ""


class _NoRedirect(HTTPRedirectHandler):
    def http_error_302(self, request, fp, code, message, headers):  # noqa: ANN001
        raise HTTPError(request.full_url, code, message, headers, fp)

    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302
    http_error_308 = http_error_302


def _decode_body(raw: str, content_type: str) -> Any:
    if "json" in content_type.lower() or raw.lstrip().startswith(("{", "[")):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return raw


def check(check_id: str, status: str, summary: str, **evidence: Any) -> dict[str, Any]:
    return redact(
        {
            "id": check_id,
            "status": status,
            "summary": summary,
            "evidence": evidence,
        }
    )


def classify_project_isolation(
    owner_project_id: int,
    peer_project_list_status: int,
    peer_projects: Any,
    peer_direct_status: int,
) -> dict[str, Any]:
    """Classify whether a peer identity can discover or open another project."""
    items = peer_projects.get("results", []) if isinstance(peer_projects, dict) else peer_projects
    items = items if isinstance(items, list) else []
    visible_ids = {item.get("id") for item in items if isinstance(item, dict)}
    leaked = owner_project_id in visible_ids or peer_direct_status == 200
    if leaked:
        return check(
            "project_isolation",
            "unsupported",
            "同一组织的身份可发现或直接访问其他身份项目，社区版原生权限不能承担学生隔离。",
            list_status=peer_project_list_status,
            owner_project_visible=owner_project_id in visible_ids,
            direct_access_status=peer_direct_status,
        )
    if peer_project_list_status == 200 and peer_direct_status in {403, 404}:
        return check(
            "project_isolation",
            "supported",
            "身份无法发现且无法直接访问其他身份项目。",
            list_status=peer_project_list_status,
            direct_access_status=peer_direct_status,
        )
    return check(
        "project_isolation",
        "limited",
        "无法从当前响应确定可靠的用户级项目隔离。",
        list_status=peer_project_list_status,
        direct_access_status=peer_direct_status,
    )


def _id_from(result: HttpResult) -> int | None:
    return result.body.get("id") if isinstance(result.body, dict) else None


def _list_from(result: HttpResult) -> list[dict[str, Any]]:
    body = result.body
    if isinstance(body, dict):
        body = body.get("results", [])
    return body if isinstance(body, list) else []


def _signup(base_url: str, alias: str, password: str) -> tuple[HttpClient, HttpResult]:
    browser = HttpClient(base_url, cookies=True)
    page = browser.request("GET", "/user/signup/")
    csrf = browser.csrf_token()
    if page.status != 200 or not csrf:
        return browser, page
    email = f"probe-{alias}-{secrets.token_hex(5)}@example.invalid"
    result = browser.request(
        "POST",
        "/user/signup/?next=/projects/",
        form={"email": email, "password": password, "csrfmiddlewaretoken": csrf},
        follow_redirects=False,
    )
    return browser, result


def _session_evidence(browser: HttpClient, project_id: int | None, task_id: int | None) -> dict[str, Any]:
    whoami = browser.request("GET", "/api/current-user/whoami")
    projects = browser.request("GET", "/api/projects/?page_size=100")
    direct = browser.request("GET", f"/api/projects/{project_id}/") if project_id else HttpResult(0, {}, {}, "")
    task_page = (
        browser.request("GET", f"/projects/{project_id}/data?task={task_id}", follow_redirects=False)
        if project_id and task_id
        else HttpResult(0, {}, {}, "")
    )
    return {
        "whoami_status": whoami.status,
        "projects_status": projects.status,
        "projects": projects.body,
        "direct_status": direct.status,
        "task_page_status": task_page.status,
        "task_page_location": task_page.headers.get("location", ""),
    }


def run_probe(base_url: str, api_token: str, *, live: bool = False) -> dict[str, Any]:
    api = HttpClient(base_url, api_token)
    checks: list[dict[str, Any]] = []

    health = api.request("GET", "/health")
    version = api.request("GET", "/api/version/")
    whoami = api.request("GET", "/api/current-user/whoami")
    checks.append(check("health", "supported" if health.status == 200 else "error", "服务健康检查", http_status=health.status))
    checks.append(check("version", "supported" if version.status == 200 else "error", "版本接口", http_status=version.status, response=version.body))
    checks.append(check("service_token", "supported" if whoami.status == 200 else "unsupported", "服务 Token 认证", http_status=whoami.status))

    root = api.request("GET", "/")
    frame_headers = {key: root.headers.get(key, "") for key in ("x-frame-options", "content-security-policy")}
    frame_status = "limited" if frame_headers["x-frame-options"] or "frame-ancestors" in frame_headers["content-security-policy"] else "supported"
    checks.append(check("iframe_headers", frame_status, "网页嵌入响应头检查（仍需浏览器 E2E 验证 Cookie）", http_status=root.status, headers=frame_headers))

    if not live:
        checks.append(check("live_mutations", "not_run", "未启用 --live，仅完成只读能力探测。"))
        return _report(base_url, version.body, checks, live=False)

    if not api_token:
        checks.append(check("live_mutations", "blocked", "实时实验需要 LABEL_STUDIO_PROBE_API_TOKEN。"))
        return _report(base_url, version.body, checks, live=True)

    label_config = '<View><Text name="text" value="$text"/><Choices name="label" toName="text"><Choice value="正确"/><Choice value="错误"/></Choices></View>'
    project_a = api.request("POST", "/api/projects/", json_body={"title": "probe-profile-a", "label_config": label_config})
    project_b = api.request("POST", "/api/projects/", json_body={"title": "probe-profile-b", "label_config": label_config})
    project_a_id, project_b_id = _id_from(project_a), _id_from(project_b)
    imported = api.request(
        "POST",
        f"/api/projects/{project_a_id}/import",
        json_body=[{"data": {"text": "能力探针任务 A"}}, {"data": {"text": "能力探针任务 B"}}],
    ) if project_a_id else HttpResult(0, {}, {}, "")
    tasks = api.request("GET", f"/api/projects/{project_a_id}/tasks?page_size=10") if project_a_id else HttpResult(0, [], {}, "")
    task_items = _list_from(tasks)
    task_ids = [item.get("id") for item in task_items if item.get("id")]
    service_ok = project_a.status == 201 and project_b.status == 201 and imported.status in {200, 201} and bool(task_ids)
    checks.append(check(
        "service_project_task_api",
        "supported" if service_ok else "unsupported",
        "服务账号创建项目并导入任务",
        project_create_statuses=[project_a.status, project_b.status],
        import_status=imported.status,
        imported_task_count=len(task_ids),
    ))

    user_alias = f"probe-api-{secrets.token_hex(5)}"
    user_api = api.request(
        "POST",
        "/api/users/",
        json_body={"email": f"{user_alias}@example.invalid", "username": user_alias},
    )
    checks.append(check(
        "user_creation_api",
        "limited" if user_api.status == 201 else "unsupported",
        "用户 API 可创建组织成员，但官方序列化器不接收密码，不能直接建立隐藏网页登录身份。",
        http_status=user_api.status,
        password_field_supported=False,
    ))

    password = "Probe-only-" + secrets.token_urlsafe(12)
    browser_a, signup_a = _signup(base_url, "a", password)
    browser_b, signup_b = _signup(base_url, "b", password)
    a = _session_evidence(browser_a, project_a_id or 0, task_ids[0] if task_ids else 0)
    b = _session_evidence(browser_b, project_a_id or 0, task_ids[0] if task_ids else 0)
    sessions_ok = signup_a.status in {301, 302} and signup_b.status in {301, 302} and a["whoami_status"] == 200 and b["whoami_status"] == 200
    checks.append(check(
        "web_sessions",
        "limited" if sessions_ok else "unsupported",
        "网页表单可建立独立 Cookie 会话，但不是稳定的后端身份 API，跨源 iframe 还受 SameSite/CSRF 约束。",
        signup_statuses=[signup_a.status, signup_b.status],
        whoami_statuses=[a["whoami_status"], b["whoami_status"]],
        direct_task_statuses=[a["task_page_status"], b["task_page_status"]],
    ))
    checks.append(classify_project_isolation(project_a_id or -1, b["projects_status"], b["projects"], b["direct_status"]))

    annotation_statuses: list[int] = []
    annotator_ids: list[int | None] = []
    if task_ids and sessions_ok:
        for browser, task_id in zip((browser_a, browser_b), task_ids[:2], strict=False):
            csrf = browser.csrf_token()
            result = browser.request(
                "POST",
                f"/api/tasks/{task_id}/annotations/",
                json_body={"result": [], "was_cancelled": True, "ground_truth": False},
                extra_headers={"X-CSRFToken": csrf, "Referer": browser.base_url},
            )
            # JSON API uses CSRF for session auth; a 403 is material evidence.
            annotation_statuses.append(result.status)
            annotator_ids.append(result.body.get("completed_by") if isinstance(result.body, dict) else None)
    traceable = len(set(item for item in annotator_ids if item is not None)) == 2
    checks.append(check(
        "annotation_attribution",
        "supported" if traceable else "limited",
        "两个网页登录身份提交标注并检查 annotator 可追溯性。",
        http_statuses=annotation_statuses,
        distinct_annotators=traceable,
    ))

    return _report(base_url, version.body, checks, live=True)


def _report(base_url: str, version: Any, checks: list[dict[str, Any]], *, live: bool) -> dict[str, Any]:
    statuses = {item["id"]: item["status"] for item in checks}
    if statuses.get("project_isolation") == "unsupported":
        strategy = "per_profile_project_with_same_origin_gateway"
        decision = "Label Studio CE 不能直接承担档案隔离；必须由标注星图后端白名单网关限制项目/任务，且不可暴露管理页。"
    elif statuses.get("project_isolation") == "supported" and statuses.get("web_sessions") in {"supported", "limited"}:
        strategy = "per_profile_hidden_identity"
        decision = "可继续验证每档案隐藏身份和同源会话桥。"
    else:
        strategy = "keep_separate_login_until_gateway_verified"
        decision = "证据不足，暂不移除 Label Studio 独立登录。"
    parsed = urlparse(base_url)
    return redact({
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": {"origin": f"{parsed.scheme}://{parsed.netloc}", "version": version},
        "live": live,
        "checks": checks,
        "decision": {"strategy": strategy, "summary": decision},
    })


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe Label Studio 1.23 integration capabilities.")
    parser.add_argument("--base-url", default=os.getenv("LABEL_STUDIO_PROBE_URL", "http://127.0.0.1:18080"))
    parser.add_argument("--api-token", default=os.getenv("LABEL_STUDIO_PROBE_API_TOKEN", ""))
    parser.add_argument("--live", action="store_true", help="Run disposable mutating checks against an isolated instance.")
    parser.add_argument("--output", type=Path, help="Optional JSON report path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    report = run_probe(args.base_url, args.api_token, live=args.live)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if any(item["status"] == "supported" for item in report["checks"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
