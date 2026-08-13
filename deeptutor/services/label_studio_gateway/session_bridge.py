from __future__ import annotations

import hashlib
import hmac
import os

import httpx


class LabelStudioSessionBridge:
    """Maintain server-side LS browser cookies; credentials never reach JS."""

    _cookies: dict[str, dict[str, str]] = {}

    def __init__(self, base_url: str, profile_id: str, email: str):
        self.base_url = base_url.rstrip("/")
        self.profile_id = profile_id
        self.email = email

    def _password(self) -> str:
        secret = os.environ.get("LABEL_STUDIO_BRIDGE_SECRET") or os.environ.get("LABEL_STUDIO_API_TOKEN")
        if not secret:
            raise RuntimeError("需要配置 LABEL_STUDIO_BRIDGE_SECRET")
        digest = hmac.new(secret.encode(), self.profile_id.encode(), hashlib.sha256).hexdigest()
        return f"Dt!{digest[:28]}a9"

    async def _auth(self, client: httpx.AsyncClient) -> None:
        page = await client.get("/user/login/")
        csrf = client.cookies.get("csrftoken", "")
        if page.status_code != 200 or not csrf:
            raise RuntimeError("Label Studio 登录页不可用")
        form = {"email": self.email, "password": self._password(), "csrfmiddlewaretoken": csrf}
        login = await client.post("/user/login/?next=/projects/", data=form, headers={"Referer": f"{self.base_url}/user/login/"})
        if login.status_code not in {301, 302}:
            signup_page = await client.get("/user/signup/")
            csrf = client.cookies.get("csrftoken", "")
            if signup_page.status_code != 200 or not csrf:
                raise RuntimeError("Label Studio 隐藏身份登录失败，且未开放注册")
            signup = await client.post("/user/signup/?next=/projects/", data={**form, "csrfmiddlewaretoken": csrf}, headers={"Referer": f"{self.base_url}/user/signup/"})
            if signup.status_code not in {301, 302}:
                raise RuntimeError("Label Studio 隐藏身份创建失败")

    async def forward(self, method: str, path: str, *, headers: dict[str, str], body: bytes) -> httpx.Response:
        cookies = self._cookies.get(self.profile_id, {})
        async with httpx.AsyncClient(base_url=self.base_url, cookies=cookies, timeout=30.0, follow_redirects=False) as client:
            if not client.cookies.get("sessionid"):
                await self._auth(client)
            csrf = client.cookies.get("csrftoken", "")
            forwarded = {key: value for key, value in headers.items() if key.lower() in {"accept", "content-type", "user-agent", "x-requested-with"}}
            if csrf and method.upper() not in {"GET", "HEAD", "OPTIONS"}:
                forwarded["X-CSRFToken"] = csrf
                forwarded["Referer"] = f"{self.base_url}/"
            response = await client.request(method, path, content=body, headers=forwarded)
            self._cookies[self.profile_id] = {cookie.name: cookie.value for cookie in client.cookies.jar}
            return response
