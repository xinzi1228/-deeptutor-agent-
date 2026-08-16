# 交接：Label Studio 专业模式代理修复（react-app 资源 404 → 白屏）

> 日期：2026-08-16。用途：压缩上下文后继续修复"专业模式选任务后没反应/白屏"。
> 这是**进行中的 bug 修复**，文件已改但**未 commit**（git status 为 M）。

---

## 一、问题现象

专业模式（Label Studio 1.23 嵌入）选择任务后：
- 早期：iframe 白屏，控制台报 `react-app/runtime.js 404`、`/react-app/main.js 404`、`jQuery is not defined`、双重前缀 `/proxy/api/v1/label-studio/proxy/...`。
- 根因：Label Studio 1.23 前端用绝对路径 `/react-app/*` 加载 React 应用，代理网关 `_rewrite_text` 只重写了 `/static/` `/api/` `/projects/` `/user/`，**漏了 `/react-app/`** → 浏览器请求 `127.0.0.1:3782/react-app/...` → Next.js 404 → React 不加载 → 白屏。

## 二、已做的修复（未提交，M 状态）

**文件**：`deeptutor/api/routers/label_studio_gateway.py`

**修改 1**：`_rewrite_text()`（约 L221-239）加 react-app 重写 + 双重前缀归一化：
```python
pairs = (
    ('"/static/', f'"{PROXY_PREFIX}/static/'),
    ("'/static/", f"'{PROXY_PREFIX}/static/"),
    ("url(/static/", f"url({PROXY_PREFIX}/static/"),
    ('"/react-app/', f'"{PROXY_PREFIX}/react-app/'),   # ← 新增
    ("'/react-app/", f"'{PROXY_PREFIX}/react-app/"),   # ← 新增
    ('"/api/', f'"{PROXY_PREFIX}/api/'),
    ...
)
for old, new in pairs:
    text = text.replace(old, new)
# 归一化双重前缀（/proxy/.../proxy/... → /proxy/...）
double = PROXY_PREFIX + PROXY_PREFIX
while double in text:
    text = text.replace(double, PROXY_PREFIX)
return text
```

**修改 2**：代理响应处理（约 L362-366）——**只对 HTML/CSS 重写，JS 直接透传**（JS 无裸路径引用且 2.5MB 重写极慢）：
```python
is_html = "text/html" in content_type
is_css = "text/css" in content_type
if is_html or is_css:
    rewritten = _rewrite_text(upstream.text)
    if is_html:
        rewritten = _inject_realtime_bridge(rewritten, path)
    content = rewritten.encode("utf-8")
```
（原代码对 `javascript` 也重写，导致 main.js 4.5s 加载 → 提速到 1.2s）

## 三、验证结果（已确认生效）

- `python -m pytest tests/api/ -k "label_studio or gateway or ls_" -q` → **17 通过**
- Python 直接请求代理 HTML：`react-app/*` 和 `/static/*` 路径全部正确带前缀，**双重前缀 0**
- JS 加载耗时：main.js **1.17s**（修复前 4.5s）、vendor.js **0.62s**（修复前 4.1s）
- 后端已重启加载修复（`start_all.bat` 或 `python -m uvicorn deeptutor.api.main:app --host 127.0.0.1 --port 8001`）

## 四、剩余工作

1. **浏览器端复验**：用户浏览器需 **Ctrl+Shift+R 硬刷新**（可能缓存旧 HTML）。用 Playwright 完整验证：解锁档案（PIN `1234`）→ 专业模式 → 选 task1 → iframe 内 Label Studio 渲染出界面。
2. **commit 修复**：`git add deeptutor/api/routers/label_studio_gateway.py` + commit（消息如 `fix: LS 1.23 react-app 代理资源 + JS 提速 (专业模式白屏)`）。
3. **后续仍可能的问题**：
   - 独立 tab 验证 Label Studio 能渲染出 `.app-wrapper` 骨架，但有 2 个 404（React 懒加载 chunk）——若影响功能需查。
   - 学习档案解锁 cookie 是 httponly，后端重启后旧 cookie 可能失效，需重新解锁（PIN `1234`，管理员重置过）。

## 五、相关背景（快速恢复）

- **服务**：8001（后端）/3782（前端 dev）/8080（Label Studio 1.23）都在跑。
- **学习档案**：`lp_dbe1f7dc11604772b9e602ed`（"哈哈哈"），PIN 已重置为 `1234`。
- **认证**：AUTH 关闭（auth.json enabled:false），所有请求当 local-admin。
- **专业模式架构**：学生经标注星图同源网关 `/api/v1/label-studio/proxy/*` 进入，不直接 iframe 8080。档案必须先解锁（`POST /api/v1/learning-profiles/{id}/unlock` 带 `{pin}` → 设置 httponly cookie `dt_learning_profile`）。
- **LS 能力报告**：`docs/label-studio-1.23-capability-report.md`（1.23 实测，网关 E2E 通过）。
- **项目状态**：本地=远程（0 未推送），8/14 竞赛优化 0.1-5.3 代码全部完成并推送（见 handoff）。

## 六、常用命令

```powershell
# 解锁档案（Python 脚本验证用）
python -c "import http.cookiejar,json,urllib.request; cj=http.cookiejar.CookieJar(); o=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); p=json.dumps({'pin':'1234'}).encode(); o.open(urllib.request.Request('http://127.0.0.1:8001/api/v1/learning-profiles/lp_dbe1f7dc11604772b9e602ed/unlock',data=p,headers={'Content-Type':'application/json'},method='POST')); print('ok')"

# 验证代理 HTML 资源路径
# 见 %TEMP%\opencode\verify_fix.py

# 测试
python -m pytest tests/api/ -k "label_studio or gateway or ls_" -q
```
