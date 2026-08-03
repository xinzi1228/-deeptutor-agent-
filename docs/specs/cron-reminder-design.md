# 定时学习提醒（cron 工具验证 + 演示）设计

> 状态: 设计已获用户批准
> 日期: 2026-08-03

---

## 1. 背景与目标

探索确认：**`cron` 工具已完整实现**（`cron_tool.py` + `CronTool` 注册 + always_on + `agentic_pipeline` 注入 `_cron_owner` + `execute_job` 到点用 Coach 生成提醒写进会话）。功能链路全通，但：

- **无测试覆盖**（`tests/` 无 cron 工具测试）——功能不可信、无回归保护
- **PERSONA 未提示 Coach 使用**——Coach 遇到"定时提醒我"可能不用该工具
- **未端到端验证**——本地 demo 是否真能跑通"注册→到点→提醒进会话"未实测

**目标**：让定时提醒功能**可信 + 可演示**。聚焦验证与提示词，不新写功能代码。

## 2. 设计决策汇总

| # | 维度 | 决策 |
|---|------|------|
| 1 | 范围 | 补测试 + PERSONA 提示 + 端到端验证（不新写功能代码） |
| 2 | 测试 | `tests/tools/test_cron_tool.py`，monkeypatch `get_cron_service` 隔离 |
| 3 | 提示词 | PERSONA 增加"定时提醒用 cron 工具"规则（含教学提醒文案风格） |
| 4 | 验证 | CLI/Playwright 实测 30 秒提醒链路 |

## 3. 测试：`tests/tools/test_cron_tool.py`

**核心**：`run_cron_action` 是纯函数，依赖 `get_cron_service()` 单例。用 monkeypatch 换 fake 服务。

覆盖：
1. `action="list"` 无任务 → ok + "No scheduled tasks"
2. `action="schedule"` 用 `every_seconds` → 调用 service.add_job（fake 记录调用参数 + 返回 CronJob）→ ok + 含 job id
3. `action="schedule"` 缺 message → 失败
4. `action="schedule"` 同时给 at+every → 失败（"exactly one of"）
5. `action="cancel"` 有效 job_id → ok；无效 → 失败
6. `_cron_owner` 缺失 → "not available in this context"
7. `_cron_in_context=True` 时 schedule → 拒绝（防从定时任务内再注册）

Fake 服务：内存 dict，实现 `list_jobs`/`add_job`/`cancel_job`（owner_key 过滤）。

## 4. PERSONA 提示词

`PERSONA.md` 交互规范加规则：

```markdown
- 用户要求定时提醒/预约时，用 `cron` 工具注册（action=schedule）：`every_seconds`（至少30秒，演示用）或 `at`（ISO时间）。提醒文案写教学风格，如"该练标注了——上次在边界框上 F1 只有50%，今天巩固一下？"
```

同步 workspace 副本。

## 5. 端到端验证

CLI 或 Playwright 实测：
1. 对话里说"30 秒后提醒我练标注"
2. Coach 应调 `cron` 工具注册 every-30s job
3. 等 ~35 秒 → 会话出现 Coach 主动提醒（`_execute_chat_job` 生成）
4. 验证提醒文案是教学风格

## 6. 明确不做

- 不新写 cron 功能代码（工具已存在）
- 不做前端定时任务管理 UI（P1 另项）
- 不做"连续 N 天未练自动注册"（需状态检测，复杂，另项）

## 7. 风险

- `run_cron_action` 内部 `get_cron_service()` 是单例——测试用 monkeypatch 模块级函数，不影响真实服务
- 端到端验证依赖 LLM（Coach 是否调用 cron 工具）——若 Coach 不主动调，提示词修正后重试
- 演示提醒间隔 30s（最小），demo 会话需保持打开才能看到追加的提醒消息
