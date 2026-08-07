# 第三轮优化设计：借鉴 DeerFlow（Super Agent Harness）

> 日期：2026-08-07。来源：clone `stophobia/deerflow2.0-enhanced`（DeerFlow 2.0 完整代码）+ `coolclaws/deerflow-book`（源码解析，27 章）。DeerFlow = 字节开源 Super Agent Harness（Lead Agent 编排 + 15 中间件 + 记忆 + 沙箱 + Skills + 子代理）。**结论：我们赢在领域层（教学法/诊断/评估/记忆分区），DeerFlow 赢在工程加固层（循环/超时/中断硬护栏 + 调度）——借鉴其工程加固。**

## 关键事实核查
- **DeerFlow 的 `reflection/` 与反思无关**（只是 importlib 动态解析）。我们已有更丰富的"教学反思"（verify_output / evaluate_teaching_plan / verify_foresight / improve_teaching_flow）。**不仿其 reflection**。
- 真正值得抄的是：硬性防循环中间件、类型化澄清中断、子代理调度加固、记忆 facts 置信度、长会话摘要+义务重注入。

## 借鉴点 E1–E8（落地映射）

### E1. 循环检测硬护栏 ⭐ S 成本
**DeerFlow**（`loop_detection_middleware.py:124-209`）：每轮对 tool_calls 做 (name+args) 排序哈希，滑动窗口 20 内同哈希 ≥3 次注入警告、≥5 次强剥 tool_calls 逼出文本。
**我们的落地**：`agent_loop.py` `_run_loop`（`:243`）维护 `deque[maxlen=20]`，每轮 `(tool_name, json.dumps(args, sort_keys=True))` 哈希；≥3 次塞中文 system 提醒（"你已重复调用 {tool} 相同参数 N 次，停止并基于已有结果总结"）；≥5 次强制 finish。
**为何重要**：教练反复 `annotation_check`/`delegate_to_expert`/`kb_search` 同参数会卡死，教学场景学生流失。
**测试**：agent_loop 测试注入重复 tool_call 序列 → 断言警告注入 + 强制结束。

### E2. 澄清类型化 + 中断 ⭐ M 成本
**DeerFlow**（`clarification_middleware.py:91-129` + `prompt.py:167-234`）：typed `ask_clarification`（missing_info/ambiguous_requirement/approach_choice/risk_confirmation/suggestion），一次调用 `goto=END` 中断整轮等用户。
**我们的落地**：`route_input` 的 `confuse` 分支已有 `ask_user` 暂停。升级：`ask_user` 输出结构化 `{question, clarification_type, options}`，前端渲染选项按钮（对齐 render_ui 卡片）；AgentLoop 检测到该调用即结束本轮。PERSONA「输入分诊」段强化"CLARIFY→诊断→教学"。
**为何重要**："诊断优先"是核心教学法（PERSONA:44）。提示词说不算数，**工具+中断机制才算**。

### E3. 子代理调度加固（timeout + 截断 + 进度事件）M 成本
**DeerFlow**（`subagent_limit_middleware.py:40-67` + `executor.py` + `task_tool.py:132-195`）：单轮 task 调用 >max 截断；双线程池 + timeout；`task_started/running/completed` 流式事件。
**我们的落地**（delegate_expert_tool.py）：
1. (M) 加 timeout（如 60s 超时降级单轮 complete fallback，已有 `:216` fallback）+ 单轮 delegate 调用 >2 截断
2. (L) 后台线程跑专家 + StreamBus 发 `task_running` 事件，前端展示"专家 X 分析中"；可并行派 grading_expert + struggle_detective
**为何重要**：竞赛 6 专家评审天然可并行；串行 5 轮 = 学生长时间空白等待。

### E4. 记忆 facts 置信度 + token 预算注入 M 成本
**DeerFlow**（`memory/updater.py:404-432` + `memory/prompt.py:186-300`）：facts 带 category/confidence（≥0.7 才存、按置信度淘汰至 100 条）；注入时 tiktoken 精确计数、置信度降序、2000 token 预算内装多少给多少。
**我们的落地**：
- `Document` 条目加 `confidence`（0-1）/`source` 字段（向后兼容，前端 memory 页可不显示）
- `read_memory`/`read_bucket` 注入时按置信度降序 + token 预算截断（现 `store.py:106-115` 全量拼接）
- `write_learning_record` 落盘要求 LLM 给 confidence
**为何重要**：教学判定（readiness gate / verify_foresight）本质是置信度决策——"疑似掌握 vs 确定掌握"才能驱动 advance/retreat 门控。

### E5. 长会话摘要 + 关键义务重注入 M 成本
**DeerFlow**（SummarizationMiddleware + `todo_middleware.py:56-91`）：token/messages/fraction 触发摘要，保留最近 N 条，AI/Tool 对不拆；`write_todos` 被摘要挤出窗口时重注入提醒。
**我们的落地**：
- `agent_loop.py` `_fold_context_checkpoint`（`:352`，现只 snip 单条 tool 结果）之上加对话级摘要：轮数 >40 或 token >80% 窗口时压缩最旧 60% 为 `[对话摘要]` system 消息
- 仿 TodoMiddleware：若 `write_learning_record`/`log_decision` 历史被摘要挤出，而 learning store 尚有未落盘里程碑 → 重注入"你有 N 个教学里程碑未落盘，请补录"
**为何重要**：45-60 分钟标注教学必然超窗；解决教练长会话后忘记落盘（PERSONA:58-63 硬纪律被挤出）。

### E6. 工具错误→错误消息让 loop 继续 S 成本
**DeerFlow**（`tool_error_handling_middleware.py:19-66`）：工具异常 → error ToolMessage（截断 500 字符）让 loop 继续。
**我们的落地**：工具执行层异常时返回结构化"工具 X 失败：原因 + 建议替代"而非中断整轮。
**测试**：mock 工具抛异常 → loop 继续 + 错误消息注入。

### E7. Dangling tool call 修补 S 成本
**DeerFlow**（`dangling_tool_call_middleware.py:36-88`）：用户中断/取消产生的半截 tool_calls → 插入合成 error ToolMessage。
**我们的落地**：构造消息前预处理，检测 AI 有 tool_calls 但缺 ToolMessage → 插入"该调用被中断，未返回结果"占位。

### E8. 会话临时信息清洗 S 成本
**DeerFlow**（`updater.py:179-213`）：不持久化上传事件等会话临时物。
**我们的落地**：`write_learning_record` 落盘前清洗"任务图文件名/本次标注数据"等会话临时物，只存可复用能力结论。
**为何重要**：防止下次会话引用已失效的会话内文件。

## 不借鉴
- reflection（命名陷阱，无真实反思）
- plan-mode todo（teaching_flow 已有等价物）
- deferred tool_search（deferred registry 已有等价物）

## 优先级
| 优先级 | 项 | Effort | 说明 |
|--------|----|--------|------|
| **P0** | E1 循环检测 + E6 工具错误恢复 | S | 防卡死，教学可靠性 |
| P1 | E2 澄清类型化 + E4 记忆 confidence | M | 教学法强化 + 判定标尺 |
| P1 | E3 子代理 timeout/截断（M 部分） | M | 等待体验 |
| P2 | E5 摘要 + E7 修补 + E8 清洗 | S/M | 长会话健壮性 |

## 实施顺序建议
本会话优先 E1+E6（S 成本立竿见影），后续 E2/E4（教学价值高），再 E5/E3。
