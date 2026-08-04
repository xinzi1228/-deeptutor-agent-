# 定时任务管理 UI 设计

> 状态: 设计已获用户批准
> 日期: 2026-08-04

---

## 1. 背景与目标

Coach 已能用 `cron` 工具注册定时提醒（schedule/list/cancel），`CronService` 功能完整（add/list/cancel/remove + at/every/cron 调度 + 运行历史）。但**用户无法在界面管理**定时任务——看不到已注册任务、不能启停/删除。

**目标**：新增「定时任务」管理页，让用户查看/启停/删除自己的 cron 任务，与定时提醒配套形成闭环。

**来源**：差距分析 §十二③（定时任务管理 UI）。

## 2. 设计决策汇总

| # | 维度 | 决策 |
|---|------|------|
| 1 | 后端 | 新增 `deeptutor/api/routers/cron.py`（list/delete/patch 三个 REST 端点） |
| 2 | 前端 | 侧边栏 Secondary NAV 加「定时任务」，路由 `/tasks`（utility 下新建 tasks 目录） |
| 3 | 启停 | CronService 加 `set_job_enabled(job_id, enabled)` 方法（改 enabled + _save） |
| 4 | owner 隔离 | 只列/操作当前用户的 chat 任务（owner.kind=chat + user scope 过滤） |
| 5 | 运行历史 | 前端展示 last_status/next_run/last_error |

## 3. 后端：`deeptutor/api/routers/cron.py`

**新增方法**（`deeptutor/services/cron/service.py`）：
```python
def set_job_enabled(self, job_id: str, enabled: bool, *, owner_key: str | None = None) -> bool:
    """Toggle a job's enabled flag (persisted)."""
    self._load()
    job = self._jobs.get(job_id)
    if job is None:
        return False
    if owner_key is not None and job.owner.key != owner_key:
        return False
    job.enabled = bool(enabled)
    self._save()
    self._wake.set()
    return True
```

**新路由**（`deeptutor/api/routers/cron.py`）：
```python
router = APIRouter()

def _owner_key_from_request() -> str:
    """Resolve the current chat user's owner key for job scoping."""
    # chat 任务的 owner.key = f"chat:{user_id or 'local-admin'}"
    return "chat:local-admin"  # local run: admin scope

@router.get("/cron/jobs")
async def list_jobs() -> dict[str, Any]:
    service = get_cron_service()
    jobs = service.list_jobs(owner_key=_owner_key_from_request())
    return {"jobs": [_job_to_dict(j) for j in jobs]}

@router.delete("/cron/jobs/{job_id}")
async def delete_job(job_id: str) -> dict[str, Any]:
    service = get_cron_service()
    if service.cancel_job(job_id, owner_key=_owner_key_from_request()):
        return {"ok": True}
    return {"ok": False, "error": "任务不存在或无权删除"}

@router.patch("/cron/jobs/{job_id}")
async def toggle_job(job_id: str, payload: JobToggleRequest) -> dict[str, Any]:
    service = get_cron_service()
    if service.set_job_enabled(job_id, payload.enabled, owner_key=_owner_key_from_request()):
        return {"ok": True, "enabled": payload.enabled}
    return {"ok": False, "error": "任务不存在或无权操作"}
```

**注意**：本地单机模式 owner_key 固定 `chat:local-admin`（demo 会话 owner.user_id=local-admin）。多用户场景需从 `user_context` 解析——读 `deeptutor/multi_user` 的当前用户获取。设计先做 local-admin（单机演示），多用户留待后续。

**`_job_to_dict`**：CronJob → dict（id/name/message/schedule/next_run/last_status/last_error/enabled）。

**测试**：`tests/api/test_cron_router.py` — list 空/非空、delete 存在/不存在、toggle 启停。

## 4. 前端「定时任务」页

**路由**：`web/app/(utility)/tasks/page.tsx`
**侧边栏**：Secondary NAV 加「定时任务」/tasks，图标 Clock

**组件**：任务卡片列表
- 每卡：名称 + 调度描述（每 30 秒/每天 9 点）+ 状态徽章（启用绿/停用灰）+ 下次运行时间 + 上次状态 + 上次错误
- 操作：启停开关 + 删除按钮
- 空态："暂无定时任务——和教练说'30 秒后提醒我练标注'即可创建"

**数据**：`web/lib/cron-api.ts` — `getCronJobs()` / `deleteCronJob(id)` / `toggleCronJob(id, enabled)`

## 5. 测试

| 层 | 测试 |
|----|------|
| 后端 | `tests/api/test_cron_router.py`：list/delete/toggle |
| 后端 | `tests/services/test_cron_service.py`：set_job_enabled 新方法（或并入现有 cron service 测试） |
| 前端 | tsc + build |
| 冒烟 | Playwright：先让 Coach 注册一个 30s 提醒 → 打开 /tasks → 看到任务 → 停用/删除 |

## 6. 明确不做

- 不做创建任务的 UI（创建走 Coach cron 工具——设计保持"Coach 管创建、界面管管理"）
- 不做多用户 owner 解析（单机 local-admin，多用户后续）
- 不做运行历史详情页（列表展示 last_status/last_error 足够）

## 7. 风险

- owner_key 硬编码 local-admin——单机演示 OK，多用户部署需接 user_context
- `set_job_enabled` 是 service 新方法，需测试（不影响现有 add/cancel）
- 停用任务后 `_seconds_until_next_due` 已过滤 `job.enabled`，不会触发（service 已处理）
