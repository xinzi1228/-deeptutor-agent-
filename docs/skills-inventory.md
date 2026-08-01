# 技能与工作流全面目录

## 总览

我们项目下共有 **19 个 skill**，来自 5 个来源。按用处分 4 类：

| 类别 | 数量 | 来源 |
|------|------|------|
| 教学法核心 | 7 | SenmuuuuW (147⭐) + full-stack-skills |
| 教学可视化与资源 | 5 | andyhuo520 + full-stack-skills + mattpocock |
| 开发者工具 | 4 | DeepTutor 内置 + mattpocock |
| 记忆与基础设施 | 3 | DeepTutor 内置 + ClawHub |

---

## 一、教学法核心（7 个）

### 1. universal-diagnostic-tutor ⭐⭐⭐
- **来源**: SenmuuuuW (GitHub, 147 stars)
- **一句话**: 诊断优先的通用 AI 导师，80+ 引用协议
- **核心特点**:
  - 先诊断再教学，不给答案优先的输出
  - SKILL.md 只做路由器，80+ 个独立协议在 `references/` 中
  - 4 种教学模式：Auto / Zero-Base / Standard / Advanced
  - 支持 `/tutor` `/practice` `/diagnose-gap` 等 10 个斜杠指令
- **我们能用的**:
  - **错误到干预映射** (`error_to_intervention_protocol.md`)：9 种错误类型 → 对应教学策略，可直接用于标注评测反馈
  - **准备就绪门控** (`readiness_gate_protocol.md`)：6 种推进判定（Advance / Advance with caution / Review first / Step down / Diagnose again / More practice）
  - **理解检查协议** (`understanding_check_protocol.md`)：7 种检查方式（一句话/解释回授/归类方法/预测下一步/错误发现/近迁移/自信度），比我们的 Teach-Back 更丰富
  - **练习阶梯** (`practice_ladder.md`)：7 级练习难度（识别→概念→完成→近迁移→陷阱→混合→真实应用）

### 2. tutor-practice
- **来源**: SenmuuuuW（universal-diagnostic-tutor 的入口子 skill）
- **一句话**: 练习与掌握循环，生成针对性练习 + 评分 + 错误分析
- **核心特点**:
  - 每次只出一道题（除非学生主动要题集）
  - 定性评分，不简化成对/错
  - 错误映射到精准修复，不全量回滚
  - 使用知识链接卡片（1-3 张）处理阻塞性前置依赖
- **我们能用的**: 练习生成协议 + 答案评分协议 + 学习任务循环协议

### 3. tutor-learn-path
- **来源**: SenmuuuuW
- **一句话**: 将宽泛的学习/考试目标转化为明确路线 + 第一步行动
- **核心特点**:
  - 先确认目标再建路线（不过度询问）
  - 紧凑、按学科优先的路径（命名子主题、最低掌握度、跳哪些）
  - 不构建庞大的课程地图
- **我们能用的**: 学习路径 → 我们的 Phase 0 诊断 + Phase 1 理论规划

### 4. learning-assessor
- **来源**: full-stack-skills (GitHub)
- **一句话**: 学习评估综合指导——题目设计、rubric 设计、学习分析
- **核心特点**:
  - 题目设计原则：目标对齐、难度梯度、清晰明确、公平性
  - Bloom 分类法驱动认知层次
  - 数据驱动的学习分析和个性化建议
- **我们能用的**: 
  - Rubric 设计模板 → 标注评测的分维评分
  - 题目设计规则 → 形成性评估的出题规范
  - 学习分析维度 → 个人中心的雷达图数据源

### 5. course-designer
- **来源**: full-stack-skills
- **一句话**: 课程设计——大纲、学习目标、教学计划
- **核心特点**:
  - Bloom 分类法认知目标层次
  - 知识点递进关系规划
  - 模块化课程结构设计
- **我们能用的**: 课程大纲 → 29 个技能点的教学顺序设计

### 6. teach
- **来源**: mattpocock/skills (GitHub)
- **一句话**: Workspace 驱动的文件式教学法——每个课题一个独立教学目录
- **核心特点**:
  - **MISSION.md**: 捕获学生学习的真实动机
  - **lessons/*.html**: 自包含 HTML 课程（可打印、可复用）
  - **assets/**: 可复用组件库（样式/测验/模拟器）
  - 区分 Fluency（即时）vs Storage（长期）记忆强度
  - 使用提取练习 + 间隔重复 + 交错练习
- **我们能用的**:
  - 课程目录结构 → 个人中心的学习档案
  - MISSION.md 概念 → Phase 0 诊断中的"学习动机"维度
  - 可复用 HTML 组件 → 生成可打印的标注入门指南

### 7. tutor-state-card
- **来源**: SenmuuuuW
- **一句话**: 轻量级跨会话学习状态卡片——不依赖隐藏数据库
- **核心特点**:
  - 用户可见、可复制粘贴的纯文本卡片
  - 不宣称有"持久化记忆"（不建立数据库幻觉）
  - 学习状态卡 / 学习者画像卡 / 学习任务卡 三种格式
- **我们能用的**: 学习状态卡 → `read_memory` / `write_memory` 的补充格式，给学生跨会话的可见进度

---

## 二、教学可视化与资源（5 个）

### 8. aetherviz-master ⭐⭐⭐
- **来源**: andyhuo520 (GitHub)
- **一句话**: 互动教育可视化建筑师——把任意教学主题转化为 3D 交互教学网页
- **核心特点**:
  - SVG + Three.js 融合，支持极高质量渲染
  - 7 套主题配色（物理/化学/生物/数学/天文/编程 + 默认）
  - 玻璃拟态 UI、深海科技背景
  - 多组件模板：导航栏、侧边栏、控制面板、进度条
- **我们能用的**:
  - **个人中心可视化** — 能力雷达图 + 技能树 + F1 成长曲线
  - **知识点互动展示** — 每个标注概念生成 3D 交互演示
  - **学习仪表盘** — 用其 UI 模板生成学生进度页

### 9. teaching-resource-generator
- **来源**: full-stack-skills
- **一句话**: 教学资源生成——课件、练习题、案例、学习指南
- **核心特点**:
  - PPT 课件结构设计
  - 多种题型生成（选择/填空/简答/编程）
  - 教学案例和纠错练习
- **我们能用的**: 练习题设计 → 标注练习的"理论前置测验"生成

### 10. tutor-visualize
- **来源**: SenmuuuuW
- **一句话**: 用最简单的可视化澄清学习者的当前理解盲区
- **核心特点**:
  - 最小可用视觉：文本 / ASCII / Markdown 表格 / Mermaid / 简单图
  - 只画出当前盲区需要的，不过度可视化
- **我们能用的**: 标注概念可视化 → IOU 计算示意图 / 能力地图 / F1 对比图

### 11. tutor-resource-scan
- **来源**: SenmuuuuW
- **一句话**: 紧凑主题扫描 + 可信学习资源推荐
- **核心特点**:
  - 教学优先于资源；资源服务教学
  - 区分资源的用途：直觉/正式定义/练习/实现/验证
  - 不造资源链接
- **我们能用的**: 资源扫描 → 标注领域的权威教材/标准文档推荐

### 12. scaffold-exercises
- **来源**: mattpocock/skills
- **一句话**: 分层练习脚手架——按目录结构组织练习/答案/解析
- **核心特点**:
  - `problem/` `solution/` `explainer/` 三文件结构
  - 节号 + 练习号的层次命名
- **我们能用的**: 练习目录模板 → 标注任务的分层组织（任务描述/标准答案/解析指导）

---

## 三、开发者工具（4 个）

### 13. skill-creator
- **来源**: DeepTutor 内置
- **一句话**: 元 skill——教你如何写 skill（设计原则、格式规范、测试方法）
- **核心特点**:
  - SKILL.md 前页 YAML + 正文
  - 渐进披露：正文 ≤ 500 行，长内容入 references/
  - 描述就是触发器——LLM 通过描述决定是否加载
- **我们能用的**: 我们写的新 Persona flows 就是按这个规范来的

### 14. annotation-guide
- **来源**: DeepTutor 内置（我们自己写的）
- **一句话**: 数据标注知识库——标注类型/质量指标/最佳实践/常见陷阱
- **核心特点**:
  - 4 大标注类型 + 质量指标 + 工作流
  - 懒加载、按需 `read_skill` 调取
- **我们能用的**: 这是理论教学的底层知识源，待中文化和扩展

### 15. docx / pdf / pptx / xlsx
- **来源**: DeepTutor 内置（4 个）
- **一句话**: 办公文档技能——生成 Word / PDF / PPT / Excel
- **核心特点**:
  - 通过 `code_execution` 沙箱跑 Python 脚本生成
  - 支持 Markdown 语法创建和写入
- **我们能用的**:
  - 生成标注学习报告（docx）
  - 生成教学 PPT（pptx）
  - 生成标注规范文档（pdf）
  - 导出学习数据（xlsx）

### 16. synapse
- **来源**: ClawHub
- **一句话**: 自学习记忆引擎——分析交互、提取偏好、更新画像
- **核心特点**:
  - 4 类记忆分类：Fact / Preference / Pattern / Correction
  - 每条记忆带 confidence 置信度
  - 每日学习周期 + 剖面更新
- **我们能用的**: 记忆模型 → 升级我们的 `write_memory` JSON 格式

---

## 四、其他参考项目

### education-agent-skills（未安装，已分析 5 个 skill）
- **来源**: GarethManning (GitHub, 483 stars)
- **5 个核心 skill**:
  - Retrieve-First Gate（检索优先门控）
  - Explain-First Interrogator（先解释后探问）
  - Progressive Hint Ladder（渐进提示梯）
  - Teach-Back Evaluator（教学回授计分）
  - Adaptive Hint Sequence（自适应提示序列）
- **我们能用的**: 全部已揉进 Persona 的 flow-theory.md / decision-matrix.md

### Bloom（未安装，已分析设计）
- **来源**: Li-Evan (GitHub, 214 stars)
- **核心设计**: 大纲→自适应课程→反馈→评估→总结
- **我们能用的**: 苏格拉底式、掌握门控、`???` 标注机制

### Coze 工作流合集（192 个 DAG）
- **来源**: `200+Coze 工作流合集.zip`
- **六大通用模式**: 线性处理链 / 内容生成管道 / 批量批处理 / 条件分支 / 多步迭代
- **我们能用的**: DAG 节点+连线 → Persona references 拆分结构

---

## 快速索引：需要什么功能 → 查哪个 skill

| 需求 | 对应 skill | 取什么 |
|------|----------|--------|
| **教学流程设计** | universal-diagnostic-tutor | 诊断→教学→检查→推进 的完整协议 |
| **形成性评估** | learning-assessor + readiness_gate | rubric 设计 + 6 种推进判定 |
| **错误反馈** | error_to_intervention | 9 种错误→对应教学策略 |
| **练习设计** | tutor-practice + practice_ladder | 7 级练习阶梯 + 定性评分 |
| **学习路线** | tutor-learn-path + course-designer | 目标确认→路线→第一步 |
| **可视化仪表盘** | aetherviz-master | 3D 交互网页生成 |
| **学习资料生成** | teaching-resource-generator + docx/pptx | 课件+练习题+报告 |
| **知识库** | annotation-guide + tutor-resource-scan | 标注知识 + 资源扫描 |
| **跨会话状态** | tutor-state-card + synapse | 可见卡片 + 记忆引擎 |
| **Skill 开发** | skill-creator | skill 设计规范 |
