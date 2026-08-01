# 整体回归演示报告

> 目的: 用真实多轮对话验证"诊断→理论→实践→记录"全链路, 找分模块测试发现不了的断裂
> 方式: DeepTutorApp facade 保持会话, 模拟零基础学生走完整流程

---

## 一、验证结果

| 环节 | 行为 | 状态 |
|------|------|------|
| 诊断对话 | read_memory → read_skill(flow-onboarding) → competency_map → job_analysis | ✅ |
| 理论教学 | Coach 出理解检查题(IOU极端情况), 生成交互演示(generate_iou_demo) | ✅ |
| 任务分发 | get_annotation_task + log_decision(推荐理由) | ✅ |
| 评测反馈 | annotation_check + 分回合反馈 | ✅ |
| 落盘记录 | write_learning_record + log_decision | ✅ (修复后) |
| 诊断建课 | finalize_diagnosis → brief + course_plan | ✅ (修复后) |

## 二、发现并修复的问题

### 1. Coach 多轮对话漏落盘 (关键 bug)

**现象**: Coach 走完全部教学流程但从不调 write_learning_record/log_decision,
records/decisions/brief/course_plan 全部为空。

**原因**: PERSONA 214 行 + 11 个工具 schema 全挂载, 多轮后上下文压缩,
记录工具被 Coach 当作"可选收尾"忽略。

**修复** (已提交 `b79a178a`):
- PERSONA 加第10条硬规则"每个教学里程碑必须落盘"
- **annotation_check 结果附"[必做]立即调 write_learning_record + log_decision"提示**
- **get_annotation_task 结果附"[必做]调 log_decision"提示**

**验证**: 工具结果提示策略有效 —— 回归后 records 有 diagnosis,
decisions 有 route_choice + task_recommendation。

### 2. 诊断后 brief/course_plan 不落盘

**现象**: 诊断完成但无 brief/course_plan (Coach 无建课工具)。

**修复** (已提交 `d70ef05f`):
- 新增 `finalize_diagnosis` 工具: 一次调用存 brief + rebuild 4模块课程计划
- flow-onboarding Step5 改为必调 (不调=诊断未完成)

**验证**: brief + course_plan 均正确生成。

## 三、回归脚本的经验

- `stream_turn` 事件类型是**小写**: tool_call/tool_result/content/result/done
- 工具名在 `ev.content`, 参数在 `ev.metadata.args`
- ask_user 暂停需 `runtime.submit_user_reply(turn_id, text=...)` 恢复
- 脚本剧本必须**顺着 Coach 的教学节奏**(一步一问), 不能预设跳步
- 完整流程需 5-6 回合, 每回合真实 LLM 30-90s

## 四、结论

回归演示达成目标: 发现并修复了 2 个真实问题(Coach 漏落盘/诊断不建课)。
系统经此验证, 教学行为符合设计(苏格拉底追问/硬性节奏/分回合反馈),
数据面板现在能收到真实数据。

**遗留**: Coach 的"记录"仍依赖 prompt/工具提示, 非系统强制。
若需 100% 保证, 可在 turn 结束时做后端兜底(检测里程碑未记录则自动补)。
