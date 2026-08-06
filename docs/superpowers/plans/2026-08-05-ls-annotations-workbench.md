# 议题④ Phase 3 实现规划：自建教学标注台 + 拟人化 Coach

> 目标：在现有 4 模态 iframe 工具（另一会话已建）基础上，加教学化增强 + 拟人化 Coach，形成「新手自带标注台 + LS 专业模式」分层教学闭环。**本规划拆分 3 个可独立交付的子阶段，避免与三模态会话冲突。**

## 现状（已核实）
- annotation 页 `web/app/(workspace)/annotation/page.tsx`：5 tab（图片/文本/音频/视频 = iframe `annotation_tool*.html`；pro = LS iframe 8080）
- 4 个静态工具已由另一会话建成（`web/public/annotation_tool{,_text,_audio,_video}.html` 20–29KB）——**不要重写**
- LS 后端 8080 + 工具链：`ls_create_project` / `ls_import_tasks` / `ls_check_annotations` / `render_ui ls_task_card`
- 评分：`annotation_check`（工具层，`_bbox_dict`/`_classify_dict`），**无 HTTP 端点**
- Chat：`/api/v1/ws`（unified-ws.ts 单连接）；`GET /api/v1/profile/trace-log`（教学回合审计）
- 学习记录：`write_learning_record` 工具（Coach 对话内）
- 记忆：`/api/v1/memory/buckets` 已可用

## 阶段拆分与 MVP

### Phase 3a（推荐先做，独立、低冲突、可演示）：拟人化 Coach 浮动组件
新 React 组件 `web/components/annotation/AnnotationCoach.tsx`（"use client"），挂到 annotation 页：
1. **浮动形象**：右下角圆形头像（emoji + CSS 动画呼吸/脉动），可拖拽收起。
2. **随时提问**：点开 → 气泡 + 输入框，发消息走聊天。实现选型（二选一，实施时定）：
   - 内联简易：`POST /api/v1/chat/sessions/{sessionId}/messages` 单发单收（非流式，够用）
   - 或复用 unified-ws 订阅当前会话事件（流式，工程量大）
   → **推荐内联 REST**，MVP 简单可靠。
3. **卡点主动介入**：轮询 `GET /api/v1/profile/trace-log`（或对 struggle 事件订阅），检测到最近 1 分钟有 `struggle_*` 事件 → 弹出 Coach 气泡提示（"我看到你在遮挡检测上有点卡，要我提示思路吗？"）。
4. **新手快捷键提示**：标注台常见快捷键清单悬浮卡（画框 B / 撤销 Ctrl+Z / 提交 Enter），`localStorage` 记住"不再显示"。
5. **AI 标识**：组件带「AI 助手」小徽标（合规 c 点）。

### Phase 3b：标注台教学化增强（评分反馈 + 交互）
- **新增评分 HTTP 端点** `deeptutor/api/routers/annotation.py`：
  - `POST /api/v1/annotation/check` body `{modal: image|text|video, task_type: bbox|classification|ner|... , predictions, ground_truth}` → 调 `annotation_check` 计算 → 返回 `{metrics:{f1,precision,recall}, report, diff:[...]}`（复用 `_bbox_dict`/`_classify_dict`）
- **前端实时反馈**：图片/文本工具提交时，前端把标注结果 POST 评分端点 → 绿/红框对比 GT 展示（Canvas 覆盖层）。若改 iframe 内部需与另一会话协调——**Phase 3b 启动前先确认 annotation_tool*.html 归属**；否则先做"提交 → 结果在 Coach 气泡展示"（不侵入 iframe）。
- 热键/撤销重做/缩放平移/任务导航：属于 iframe 工具改造，**列入三模态会话待办或独立 React 画布组件**（本规划不强绑）。

### Phase 3c：能力路径 + 进度可视化 + 成绩回传
- annotation 页顶部/侧栏加「当前任务在能力树位置 + 掌握度」条（复用 `GET /api/v1/profile/teaching-flow` + competency_map）。
- LS 结果回传：`ls_check_annotations` 评分 → `write_learning_record`（Coach 对话内完成，已有链路）→ 前端学习记录可视化。
- 全部回传走 Coach（总控调度），annotation 页只读展示。

## 接口契约（实施时落实）
| 能力 | 端点 | 状态 |
|------|------|------|
| Coach 提问 | `POST /api/v1/chat/sessions/{id}/messages` | 已有（chat.py） |
| 卡点检测 | `GET /api/v1/profile/trace-log` | 已有 |
| 实时评分 | `POST /api/v1/annotation/check`（新增） | **需新增** |
| 进度 | `GET /api/v1/profile/teaching-flow` | 已有 |
| 记忆区 | `/api/v1/memory/buckets/*` | 已有 |

## 冲突规避（关键）
- **不动** `annotation_tool*.html`（另一会话所有）——Phase 3a 零冲突。
- 新文件独立命名：`web/components/annotation/AnnotationCoach.tsx`；`deeptutor/api/routers/annotation.py`。
- annotation `page.tsx` 仅加一行挂载（rebase 共存）。
- 每次大版本 push 前 `git fetch + rebase`（另一会话持续推三模态改动）。

## 文件清单
- `web/components/annotation/AnnotationCoach.tsx`（Phase 3a，新）
- `web/app/(workspace)/annotation/page.tsx`（+1 挂载行）
- `deeptutor/api/routers/annotation.py` + `deeptutor/api/main.py`（注册 `/api/v1/annotation`，Phase 3b）
- `tests/api/test_annotation_check_router.py`（Phase 3b，仿 test_memory_buckets 模式）
- `web/components/annotation/AnnotationProgress.tsx`（Phase 3c）

## 验证
- 后端：`pytest tests/api/test_annotation_check_router.py -v` + 回归
- 前端：`cd web && npx tsc --noEmit`（忽略 `.next` 预存在损坏）+ `next build`（清代理）
- 冒烟：annotation 页 → Coach 出现 → 提问得答 → 标注提交评分 → 反馈

## 实施建议
- **Phase 3a 独立可交付**（本会话可启动，上下文不足则下个会话按本文档实施）。
- Phase 3b 评分端点后端部分可独立于 iframe 改造先行（后端 + 测试，前端接入待 iframe 归属确认）。
