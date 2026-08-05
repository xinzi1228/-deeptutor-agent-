# 议题⑤ 设计：输入分诊 `route_input`

> 处理"用户输入不完整 / 无关内容"。竞赛评分点：需求方案书「技术实现合理性 25 分」点名要求 *能识别模糊提问（如"这个怎么弄？"→反问"您是指传感器接线还是参数设置？"），支持 2-3 轮追问*；「交互友好性」要求分步骤、口语化、贴合高职生认知。

## 1. 调研借鉴（GitHub 成熟方案）

| 来源 | 核心机制 | 融入点 |
|------|---------|--------|
| feynman-tutor（koukekoukej-glitch） | 意图三分类：确认小问题→直接答+问展开；接上次→从进度进入；从头学→完整对话；**事实 vs 推理**（缺事实直接给，不卖关子） | `question_confirm` / `question_deep` 细分 |
| inye-adk intent clarification | **NEVER GUESS. ALWAYS ASK.**；歧义四维度（Scope/Implementation/Behavior/User）；AskUserQuestion 带选项、一次一题、直到收敛；结构化总结+用户确认；反模式清单 | PERSONA「绝不猜测」硬规则 + 澄清收敛+复述确认 |
| Vibe-learning Never-Answer | 每条回答必须以问题结尾，强制主动澄清 | 推进教学时回答以问题结尾（弱化版） |
| superpowers brainstorming | 一次一个问题、多选优先、逐节确认 | ask_user 澄清选项一次一题、给候选 |

## 2. 设计

### 2.1 组件：`route_input` 工具（新增 always_on 教学工具）

- 文件：`deeptutor/tools/route_input_tool.py`
- 输入：`user_message` + 可选 `recent_context`（最近 1-2 轮）
- 输出（结构化 JSON）：
  ```json
  {
    "category": "confuse",
    "confidence": 0.87,
    "clarify_options": ["开始新的标注练习", "查看我的学习进度", "问一个知识点"],
    "short_reply_hint": "听起来你有点不确定？我们可以…",
    "flag_struggle": true,
    "requires_confirmation": false
  }
  ```

### 2.2 category 语义与分支策略

| category | 含义 | Coach 行为 |
|----------|------|-----------|
| `task_start` | 想开始/继续练习 | teaching_flow 引导 / `get_annotation_task` 出题 |
| `answer_submit` | 提交标注/答案 | `annotation_check` 评分 |
| `question_confirm` | 一句话确认性疑问 | 直接回答 + 问要不要展开（feynman ①） |
| `question_deep` | 问知识点/规范 | standards 规范库检索 + 规范引用溯源 |
| `confuse` | 不完整/模糊 | ask_user 候选选项 + 自由输入 |
| `off_topic` | 无关内容 | 简短回应 1-2 句 + 拉回 |
| `greeting` | 寒暄 | 简短回应 + 询问学习目标 |

### 2.3 澄清流程（confuse 分支）

1. Coach 调 `route_input` 得到 `clarify_options`
2. `ask_user` 弹卡片（候选选项 + 自由输入入口）——**一次一个主题**，选项按 scope/behavior 维度生成
3. **追问上限 2 轮**；超过仍不清 → 回退 teaching_flow 当前阶段引导（"我直接给你演示一个示例任务"）
4. 澄清 ≥1 轮后：Coach **复述理解让用户确认**（inye-adk Phase 4/5 + feynman「写笔记前确认」）

### 2.4 PERSONA 输入护栏规则

- **NEVER GUESS**：用户意图不明确时必先澄清，不猜测意图
- **off_topic**：简短回应后拉回（"我们可以继续标注练习，你想练哪个任务？"）
- **question_confirm**：缺事实直接给，不卖关子
- 推进教学时回答以问题结尾（Never-Answer 弱化版，非强制全部）

### 2.5 记录与联动

- `route_input` 结果写 trace-log（category + confidence）→ 为议题③积累输入质量数据
- `confuse` 且 `flag_struggle=true` → 联动 `struggle_detect`（强化困难检测模块）

## 3. 实现与测试

- 注册 4 处：`tools/builtin/__init__.py`（import + `BUILTIN_TOOL_TYPES` + `__all__` + `CONFIGURABLE_BUILTIN_TOOL_NAMES`）+ always_on tuple + PERSONA + 冒烟
- 测试：`tests/tools/test_route_input.py`——各 category 输入样本 + 分类稳定性 + `clarify_options` 生成
- 冒烟：发"这个怎么弄？"→ 弹候选选项
- 前端：`ask_user` 选项卡片 UI 已存在，零改动

## 4. 衔接

- **议题⑥护栏**：`route_input` 是输入侧护栏的基础组件
- **议题⑦总控**：`route_input` 是统一意图分诊入口，未来可由总控 agent 接管
