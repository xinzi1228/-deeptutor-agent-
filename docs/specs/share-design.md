# 免登录分享/嵌入设计

> 状态: 设计已获用户批准
> 日期: 2026-08-04

---

## 1. 背景与目标

给评委/家长展示学习成果时，当前只能登录后看。FastGPT 等产品支持"生成免登录分享链接 + Iframe 嵌入"，让外部无需登录即可查看。

**目标**：
1. 生成免登录分享链接（token 白名单，只读）
2. 分享页无登录可看会话内容
3. 可选 Iframe 嵌入片段（嵌入任意站点）

**安全前提（关键）**：当前 `GET /api/v1/sessions/{id}` 有 `_auth` 依赖但无 owner 校验。分享不能直接暴露它——必须用**分享 token 白名单**绕过 auth，只读返回指定会话。

## 2. 设计决策汇总

| # | 维度 | 决策 |
|---|------|------|
| 1 | 分享模型 | `share_token`（secrets.token_urlsafe）+ 关联 session_id + 过期时间，存 `data/user/workspace/shares.json` |
| 2 | 创建 | `POST /api/v1/shares`（登录态，_auth）→ 生成 token |
| 3 | 读取 | `GET /api/v1/share/{token}`（**公共路由，绕过 auth**）→ 校验 token → 只读返回会话 |
| 4 | 前端 | Home 会话菜单「分享」按钮 → 复制链接；`/share/{token}` 只读页 |
| 5 | 嵌入 | 分享页即 Iframe 可嵌（`<iframe src="/share/{token}">`） |

## 3. 后端

### 3.1 分享 store

`deeptutor/services/share.py`：
```python
@dataclass
class ShareEntry:
    token: str
    session_id: str
    created_at_ms: int
    expires_at_ms: int | None  # None = 永不过期

class ShareStore:
    def __init__(self, path: Path): ...
    def create(self, session_id: str, *, ttl_seconds: int | None = None) -> ShareEntry
    def get(self, token: str) -> ShareEntry | None   # 校验存在 + 未过期
    def revoke(self, token: str) -> bool
    def list_by_session(self, session_id: str) -> list[ShareEntry]
```
- 文件 JSON 持久化（与 cron store 同风格）
- token = `secrets.token_urlsafe(16)`

### 3.2 路由 `deeptutor/api/routers/shares.py`

| 端点 | auth | 用途 |
|------|------|------|
| `POST /api/v1/shares` | `_auth` | 登录用户创建分享 → `{token, url}` |
| `DELETE /api/v1/shares/{token}` | `_auth` | 撤销分享 |
| `GET /api/v1/share/{token}` | **公共（无 _auth）** | 校验 token → 只读返回会话 |

关键：`GET /api/v1/share/{token}` 挂到**没有 `_auth` 的 include**（像 auth router 一样公共），内部校验 token → 存在且未过期 → 调 `get_session_with_messages` 返回只读数据（去掉敏感字段如 cron 元数据，或原样返回消息+内容即可）。

**测试**：`tests/api/test_shares.py` — create 返回 token、get 有效/无效/过期、revoke。

## 4. 前端

### 4.1 分享按钮
Home 会话菜单（标题栏）加「分享」按钮 → `POST /api/v1/shares` → 弹窗显示分享链接 + 复制按钮 + 可选「嵌入」显示 `<iframe>` 片段

### 4.2 只读分享页
`web/app/share/[token]/page.tsx`：
- `GET /api/v1/share/{token}` 拿会话 → 只读渲染（禁用 composer/输入）
- 复用 `chat-export` 的消息结构或简化的消息列表（时间线式只读）
- 无登录可访问（public route 页）

### 4.3 嵌入
分享页即可被 `<iframe src="分享链接">` 嵌入（无需额外代码）。前端分享弹窗提供 Iframe 片段复制。

## 5. 测试

| 层 | 测试 |
|----|------|
| 后端 | `tests/api/test_shares.py`：create/get/revoke/过期 |
| 后端 | `tests/services/test_share_store.py`：store 持久化 |
| 前端 | tsc + build |
| 冒烟 | Playwright：登录创建分享 → 复制链接 → 无登录打开链接看会话内容 |

## 6. 明确不做

- 不暴露 `GET /api/v1/sessions/{id}` 为公共（保持 _auth）
- 不做分享内交互（只读，禁评论/操作）
- 不做多用户 owner 校验（单机 local-admin，分享是全局白名单）

## 7. 风险

- **安全**：`GET /api/v1/share/{token}` 是公共路由——token 白名单是唯一保护。token 16 字节随机（足够），且必须校验过期。分享内容即该会话全部消息（教学场景，可接受）
- 前端分享页需独立路由（不依赖登录态）
- 演示时若 AUTH_ENABLED=false，分享路由也应工作（公共路由天然支持）
