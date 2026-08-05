# 议题④ 设计：Label Studio 交互借鉴 + 教学化自建标注台

> 用户定位：LS 是卖点要能演示；不套用 LS 界面，**借鉴 LS 标注交互 + 深度教学定制**；新手教学台 + LS 专业模式分层。

## 1. 现状

- LS 服务独立部署（8080），`label_studio_tool` 有 `ls_create_project`（建项目）+ `ls_check_annotations`（拉结果评分）；**缺导入任务动作**
- 前端 annotation 页 pro 模式 = iframe LS 首页（非具体任务）
- 缺口：卡片跳转具体任务、拟人化 Coach、完成检测+结果回传闭环未通

## 2. 调研结论（LS 优点全景 + 法律）

- **license Apache-2.0**（27.9k★）→ 改造合法
- **前后端分离**：React SPA + Django API，`prebuild_wo_frontend.sh` 支持 headless 后端 → 可**复用 LS 后端**（Project/Task/Annotation 数据模型 + API + webhooks + SDK），自建前端
- **LS 优点**：交互（热键/标签面板/撤销重做/缩放平移/任务导航/批量/跳过）、数据（Data Manager/多存储/多格式导入导出/预测导入）、AI（ML backend/Active Learning/Prompts）、质量（GT/Review/Agreement/评论/看板）

## 3. 架构决策

**LS 后端（数据/API/webhook 完成检测） + 自建教学标注台（借鉴 LS 交互 + 教学差异化）**

```
LS 后端（Django：任务/标注/预测数据 + REST API + webhook）
  ↕ REST API
自建教学标注台（前端）
  ├─ 新手模式：教学引导 + 实时反馈 + 拟人化 Coach
  └─ 进阶入口：LS 专业模式 iframe（保留原样）
任务数据共享 → 成绩/记录互通
```

## 4. 设计

### 4.1 交互借鉴清单（抄 LS 操作手感）
- 标注画布居中 + 标签面板（LS 布局范式）
- 热键（画框/切换标签/撤销/提交）
- 撤销/重做、缩放/平移
- 任务导航（上一个/下一个/列表侧栏）
- 批量标注、跳过任务

### 4.2 教学优化清单（LS 没有，我们加）
- **实时评分反馈**：标注过程中即时提示（边缘过近/重叠），提交后绿/红框对比 GT
- **拟人化 Coach**：浮动形象 + 随时提问对话框 + 卡点主动介入
- **能力路径驱动**：任务按 competency 解锁排序（从易到难）
- **进度可视化**：当前任务在路径中的位置 + 掌握度
- **快捷键教学提示**：新手显示可用快捷键

### 4.3 专属特色（差异化，竞赛加分）
- **AI 辅助标注教学**（LS 预测升级）：预标注正确→新手练手；预标注错误→"找错"训练（error_case 闭环）
- **三模态统一教学**：同一 Coach 教文本/图像/视频（衔接三模态规划）
- **成绩/记录互通**：LS 结果回传 → annotation_check 评分 → learning records

### 4.4 LS 后端接入
- 工具加 `import` 动作（`/api/projects/{id}/import` 导入 task_bank 任务）
- **webhook 完成检测**：LS 标注保存事件 → 触发回传评分
- **卡片跳转**：`render_ui` 出 LS 任务卡片 → 点击 `/projects/{id}/labeling?task=N`
- 图片供 LS 访问：上传或 `LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT` 指向图片目录

## 5. 实现与测试

- 后端：`ls_create_project` 加 import；新增 LS 完成检测 webhook 端点；结果回传链路
- 前端：自建标注台（图像/文本/视频三模态，借鉴 LS 交互）+ 拟人化 Coach 组件 + 任务卡片
- 测试：`tests/tools/test_ls_tools.py`（建项目/导入/拉结果/回传评分）；前端 tsc + build
- 冒烟：Coach 出题 → 卡片跳转 LS 任务 → 标注 → 完成 → 回传评分 → 反馈

## 6. 注意事项

- **不得与 LS 雷同**：交互范式借鉴，视觉/教学元素差异化
- **图片路径**：LS 任务数据须能访问图片（上传/本地目录配置）
- **webhook**：需配置 LS webhook URL（指向我们后端），注意 LS 服务可见性
- **token**：`LABEL_STUDIO_API_TOKEN` 环境变量配置
- **性能**：视频任务回传按帧评分，避免大 payload
- **三模态衔接**：标注台按 `docs/3modal-annotation-plan.md` 的三模态矩阵实现

## 7. 衔接

- 议题⑤ `route_input`：跳转/提问意图分诊
- 议题⑥ `verify_output`：评分输出护栏
- 议题③ 知识库：任务数据/规范支撑
- 议题⑦ 总控：标注会话归总控调度
- 三模态规划：`docs/3modal-annotation-plan.md`
