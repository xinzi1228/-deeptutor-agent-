# DeepTutor 数据标注教学平台 — V1 设计文档

## 概述

本项目基于 [DeepTutor](https://github.com/HKUDS/DeepTutor) 二次开发，参加
**科大讯飞 XA-202603 "面向职业教育高水平专业群建设的教学实训与岗位技能智能体开发"**
比赛。核心定位：以 **AI 数据标注工程师** 岗位为目标，构建一个覆盖
"岗位能力图谱 → 专业知识库 → 任务驱动教学 → 自适应评测反馈"
完整闭环的教学实训智能体。

---

## 一、竞赛对标总览

| 竞赛要求 | V1 目标 | 状态 |
|----------|---------|------|
| S1 人才需求分析与培养方案优化 | 招标网站/招聘平台岗位数据采集 + 趋势分析工具 | 待开发 |
| S2 职业岗位能力图谱构建 | AI数据标注工程师岗位能力树 + 思维导图可视化 | 待开发 |
| S3 岗位任务转化为学习任务 | 5类标注任务 × 3个难度等级 = 15+个学习任务 | 已有基础，待扩展 |
| S4 个性化自适应学习 | 对接 Learning Engine 掌握度计算 + 间隔复习 | 待开发 |
| 50+条专业知识库 | 6个领域 × 10条知识 = 60条结构化知识 | 待开发 |
| 场景真实性 | 真实课程数据集 + 行业标准引用 | 已有基础 |
| 功能闭环 | 标注→评测→反馈→追问→复习 全流程 | 已有基础，待优化 |
| 内容专业性 | RAG 知识库 + 国标引用 + 教材页码 | 待开发 |
| 交互友好性 | postMessage 通信 + 移动端 + 2-3轮追问 | 待优化 |

---

## 二、系统架构

```
                          ┌─────────────────────────┐
                          │     Web 前端 (Next.js)    │
                          │  ┌──────────┬──────────┐ │
                          │  │ Chat 页面 │ 标注工作台 │ │
                          │  └─────┬────┴────┬─────┘ │
                          └────────┼─────────┼───────┘
                                   │         │
                            WebSocket   postMessage
                                   │         │
                          ┌────────▼─────────▼───────┐
                          │    FastAPI 后端             │
                          │                            │
                          │  ┌──────────────────────┐ │
                          │  │   ChatOrchestrator    │ │
                          │  └────────┬─────────────┘ │
                          │           │                │
                          │  ┌────────▼─────────────┐ │
                          │  │ AgenticChatPipeline   │ │
                          │  │  ├─ annotation-coach  │ │
                          │  │  ├─ RAG (知识库)       │ │
                          │  │  └─ Learning Engine   │ │
                          │  └────────┬─────────────┘ │
                          │           │                │
                          │  ┌────────▼─────────────┐ │
                          │  │      工具层            │ │
                          │  │  ├─ annotation_check  │ │
                          │  │  ├─ get_task          │ │
                          │  │  ├─ job_analysis ★    │ │
                          │  │  ├─ competency_map ★  │ │
                          │  │  ├─ rag               │ │
                          │  │  ├─ learning_*        │ │
                          │  │  └─ label_studio_*    │ │
                          │  └──────────────────────┘ │
                          │                            │
                          │  ┌──────────────────────┐ │
                          │  │     数据层             │ │
                          │  │  ├─ task_bank.json    │ │
                          │  │  ├─ knowledge/        │ │
                          │  │  ├─ competency_tree/  │ │
                          │  │  └─ learning/         │ │
                          │  └──────────────────────┘ │
                          └────────────────────────────┘
```

---

## 三、V1 实施计划

### Phase 1: 知识体系建设 (Day 1-2)

| 任务 | 文件 | 说明 |
|------|------|------|
| 1.1 岗位能力图谱 | `deeptutor/tools/competency_tool.py` | AI数据标注工程师岗位能力树生成与查询工具 |
| 1.2 专业知识库 | `data/user/workspace/annotation_kb/` | 6大领域 × 10条 = 60条结构化知识文档 |
| 1.3 RAG 知识库导入脚本 | `scripts/build_annotation_kb.py` | 批量导入知识文档到 LlamaIndex KB |

### Phase 2: 学习引擎对接 (Day 3-4)

| 任务 | 文件 | 说明 |
|------|------|------|
| 2.1 标注技能知识点建模 | `deeptutor/learning/annotation_kp.py` | 定义标注领域 KnowledgePoint/LearningModule |
| 2.2 掌握度计算对接 | `deeptutor/tools/annotation_check.py` | 评测结果写入 LearningProgress |
| 2.3 自适应推荐逻辑 | `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` | 基于 Learning Engine 替代手动 F1 判断 |

### Phase 3: 任务库扩展 (Day 5-6)

| 任务 | 文件 | 说明 |
|------|------|------|
| 3.1 任务库扩容 | `data/user/workspace/task_bank.json` | 15+任务（5类型×3难度） |
| 3.2 分类标注 UI | `web/public/annotation_tool.html` | 新增分类任务界面 |
| 3.3 多边形标注 | `web/public/annotation_tool.html` | 新增多边形绘制模式 |

### Phase 4: 岗位分析工具 (Day 7)

| 任务 | 文件 | 说明 |
|------|------|------|
| 4.1 人才需求分析 | `deeptutor/tools/job_analysis_tool.py` | 招聘数据采集 + 趋势分析 |

### Phase 5: 体验优化 (Day 8-9)

| 任务 | 文件 | 说明 |
|------|------|------|
| 5.1 postMessage 通信 | `web/public/annotation_tool.html` + `web/app/` | 替换 localStorage |
| 5.2 移动端适配 | `web/public/annotation_tool.html` | 触摸事件支持 |
| 5.3 中文知识库 | `deeptutor/skills/builtin/annotation-guide/SKILL.md` | 中文化 + 实操案例 |

---

## 四、数据模型设计

### 4.1 岗位能力树

```python
# 岗位能力图谱节点
class CompetencyNode:
    id: str                    # "bbox-annotation"
    name: str                  # "目标检测标注"
    level: int                 # 1=岗位, 2=任务群, 3=任务, 4=技能, 5=知识点
    parent_id: str | None
    children: list[CompetencyNode]
    description: str           # 节点说明
    standards: list[str]       # 关联标准 (国标/行标)
    knowledge_points: list[str]  # 关联知识点 ID
    tasks: list[str]           # 关联练习任务 ID
```

### 4.2 标注知识点（扩展 Learning Engine）

```python
# 标注领域知识点 (继承 KnowledgePoint)
class AnnotationKnowledgePoint(KnowledgePoint):
    annotation_type: str       # bbox / polygon / keypoint / classification
    difficulty: str            # basic / intermediate / advanced
    related_tasks: list[str]   # task_bank 中的练习 ID
```

### 4.3 题库任务

```python
class AnnotationTask:
    id: str
    title: str
    type: str                  # bbox / polygon / keypoint / classification / multi_label
    difficulty: str            # easy / medium / hard
    image_url: str
    labels: list[str]
    ground_truth: dict         # 格式根据 type 不同
    knowledge_points: list[str]  # 关联知识点
    hints: list[str]           # 教学提示
```

---

## 五、交互流程

### 学生首次使用
```
学生: "我要学习数据标注"
  ↓
Coach: 展示岗位能力图谱（哪些技能要学）
  ↓
Coach: "我们先从目标检测标注开始。这是你的第一个任务：车辆检测。"
  ↓ (调用 get_annotation_task)
Coach: 展示任务详情 + 图片 + 标签说明
  ↓
学生: 打开标注工作台，画框 → 点"检查标注"
  ↓
前端: IOU 计算 + 可视化反馈
  ↓
学生: 点"问 Coach"
  ↓ (postMessage → Chat)
Coach: 调用 annotation_check 深度评测
  ↓
Coach: "你的 F1 是 85%，第3个框漏标了左侧的车。建议回看标注指南第2节关于遮挡处理的内容。"
  ↓ (调用 read_skill + rag)
Coach: 记录学习进度 (write_memory + Learning Engine)
  ↓
Coach: "你是否想再试一次这个任务，还是进入下一个难度？"
```

### 教师使用
```
教师: "分析一下 AI数据标注工程师 的岗位需求"
  ↓
系统: 调用 job_analysis_tool → 招聘数据趋势图
      + 与当前培养方案匹配度分析
  ↓
教师: "帮我生成这个学期的标注教学计划"
  ↓
系统: 基于能力图谱 + 知识库 → 自动排课大纲
```

---

## 六、技术选型

| 层面 | 技术 | 理由 |
|------|------|------|
| 后端框架 | FastAPI + DeepTutor 插件体系 | 复用现有架构 |
| LLM | DeepSeek Chat (OpenAI 兼容) | 用户已有 Key |
| 知识库 | LlamaIndex + FAISS (DeepTutor 内置) | 复用现有 RAG 管线 |
| 前端 | Next.js + Canvas API | 复用现有框架 |
| 岗位分析 | web_search + reason 工具链 | DeepTutor 内置 |
| 学习引擎 | deeptutor/learning/ | 复用间隔复习/掌握度 |

---

## 七、验收标准

| 编号 | 标准 | 验证方式 |
|------|------|---------|
| V1 | 岗位能力图谱（≥3层，≥20个节点） | 调用 competency_map 工具输出 |
| V2 | 专业知识库 ≥50条 | `deeptutor kb list` 查看 |
| V3 | 标注任务 ≥15个（5类型×3难度） | task_bank.json 条目数 |
| V4 | 自适应学习：基于历史推荐下一题 | 连续2次对话，推荐逻辑不同 |
| V5 | 功能闭环：标注→评测→反馈→追问→复习 | 端到端走通 |
| V6 | 人才需求分析：返回岗位趋势+数据来源 | job_analysis 工具输出 |
| V7 | 场景真实性：引用行业标准/教材页码 | RAG 查询返回结果含来源 |
