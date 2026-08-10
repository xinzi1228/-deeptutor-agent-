# 演示方案设计：明天向指导老师展示「标注星图」

> 日期：2026-08-10。对象：指导老师。时长：30+ 分钟（深度展示）。
> 核心思路：**我先把每个可展示功能跑成真实会话存进项目 → 明天点击侧边栏历史会话即可展示**，配合页面穿插。基于全部 26 份设计文档（14 份 superpowers/specs + 12 份 docs/specs）第一手阅读。

---

## 一、展示形式（用户确认：方案 A）

1. **对话功能** → 我提前跑成真实会话，侧边栏按编号命名（①完整教学闭环 ②AI 预标注审阅 ③专家看板 …）
2. **页面功能** → 现场切换页面展示（annotation/progress/memory/规范库/定时任务）
3. **后端功能** → 我现场用 API/脚本验证给老师看
4. **兜底** → 可选：为每条会话生成免登录分享链接（服务挂时用分享页）

## 二、展示结构（三幕）

### 第一幕 · 完整教学闭环（1 条主线会话）
诊断建课 → 出题 → 学生标注 → 像素校验评分 → 卡点介入 → 落盘 + 知识图谱更新 → 进度/雷达图

### 第二幕 · 创新点与亮点（专题会话 + 页面）
AI 预标注审阅（⭐竞赛创新点）→ 专家看板/委派 → 快捷语 + 疑问优先 → 知识库溯源 → 能力目标进度卡 → 陪伴人格/状态环

### 第三幕 · 平台能力（页面现场）
四模态标注台 → Progress（成就/热力图/教学流程面板）→ 记忆分区 → 规范库 → 定时任务管理 → 免登录分享

## 三、功能分类总表

### 第一类：我能测试 + 前端展示（对话触发）
| 功能 | 来源设计 | 展示 |
|------|---------|------|
| 诊断建课/课程计划 | knowledge-graph-design | 对话 |
| 任务引导 6 步 + 像素校验 | teaching-flow-engine-design | 对话+Progress |
| 困难检测介入 | struggle-detector-design | 对话 |
| 多专家角色 | expert-roles-design | 对话 |
| 打卡徽章/热力图 | checkin-achievements-design | Progress 页 |
| 知识图谱风险链 | knowledge-graph-design | 对话出图 |
| 对话内图表（成绩单/雷达/进度） | visualization-design | 对话出图卡 |
| 输入分诊 | input-routing-design | 发模糊话 |
| AI 标识/护栏 | output-guardrails-design | 对话可见 |
| 知识库检索/溯源 | knowledge-base-design | 问规范 |
| 记忆分区 | memory-partition-design | 记忆页 |
| 专家委派+看板 | master-orchestrator + orca-fleet | 对话 |
| 快捷语/疑问按钮 | petphrase + round2-O8 | AnnotationCoach |
| 陪伴人格/状态环 | airi + hermes | 对话 |
| 能力进度卡 | round2-O7 | 对话出卡 |
| 苏格拉底节奏 | round2-O9 | 对话 |
| 状态点/通知 | orca O1-O2 + F2 | 全站 |
| AI 预标注审阅 | 8/10 | 对话+标注台 |
| 练习卡片 quiz_card | generative-ui-design | 对话出卡 |
| 规范库/教学轨迹 | standards-trace + teaching-trace | 页面 |
| 教学流程面板 | teaching-flow-visual | Progress 页 |
| 定时任务管理页 | cron-ui-design | 页面 |

### 第二类：后端能力（API 层验证）
- tencentdb A/B（记忆护栏 + LLM 去重）
- deerflow E1-E8（循环/超时/折叠）
- round2 O1/O2/O4（路由回退/重排/缓存）
- verify_output（防编造）
- 免登录分享（生成链接）

### 第三类：只能你自己测/演示
- Label Studio 专业模式（8080 未开，需单独启动）
- 语音 agent（TTS/STT 未配置）
- 定时提醒到点（cron 等时间）
- 四模态标注台手动操作（需真人）
- quiz_card 生成时机（Coach 出题）

### 不可展示（写 md 大白话说明）
- 上游 DeepTutor 原功能（deep_solve/visualize 等已裁）
- 外部依赖（LS/语音）

## 四、我负责的准备工作

1. **跑通全部第一类会话**（Playwright/API 扮演学生，逐条触发功能）
2. **重命名会话**（侧边栏①②③编号）
3. **预置数据**（成就徽章/热力图/记忆桶）
4. **写演示脚本** `docs/demo-script.md`
5. **写不可展示清单** `docs/cannot-demo.md`（大白话）
6. **生成分享链接兜底**（可选）

## 五、验收

- 每条会话可点击展示对应功能，无打字触发
- 页面功能切换流畅
- 演示脚本每步有"点哪/讲什么/背后技术"
- 不可展示清单大白话可读
