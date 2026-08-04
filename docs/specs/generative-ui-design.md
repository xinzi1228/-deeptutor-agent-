# 生成式 UI 设计（练习卡片 quiz_card）

> 状态: 设计已获用户批准
> 日期: 2026-08-04

---

## 1. 背景与目标

**探索结论**：生成式 UI 的标准模式是 AG-UI 协议（15.1k stars，MIT）——agent 输出结构化消息（组件 JSON），前端渲染为交互组件。CopilotKit（其参考实现）用 `structured message` 让 agent 出卡片/表单。

**决策**：不引入 CopilotKit/AG-UI 重型框架，**借鉴其 structured-message 思想，落地到我们已有的 `metadata.chart` 通道**——DeepTutor 的 StreamBus 事件流 + `ChatChartCard` 已是"工具驱动 UI"模式，扩展即可。

**目标**：新增**练习卡片（quiz_card）**——agent 出题时输出结构化组件 JSON，前端渲染为可交互练习卡片（题目 + 选项 + 点击即时对错反馈）。这是教学场景最有冲击力的生成式 UI。

## 2. 设计决策汇总

| # | 维度 | 决策 |
|---|------|------|
| 1 | 模式 | 借鉴 AG-UI structured-message，落地现有 `metadata.chart` 通道 |
| 2 | 组件 | `quiz_card` 练习卡片（首个，最实用） |
| 3 | 后端 | `render_ui` 工具（校验组件 JSON → 返回 `metadata.chart`） |
| 4 | 前端 | `ChatChartCard` 扩展 `quiz_card` 类型（可交互：点击选项即时反馈） |
| 5 | 交互 | 前端本地判断对错（answer_index 在组件 JSON 里），演示流畅 |
| 6 | 提示词 | PERSONA 教 Coach 出题时用 `render_ui` 输出练习卡片 |

## 3. 组件协议（quiz_card）

借鉴 AG-UI 的 `{type, content}` 结构化消息，定义教学组件契约：

```json
{
  "type": "quiz_card",
  "data": {
    "question": "两个框完全不重叠时 IOU 是多少？",
    "options": ["0", "0.5", "1", "无法计算"],
    "answer_index": 0,
    "explanation": "无交集 → intersection=0 → IOU=0",
    "knowledge_point": "IOU计算与评测",
    "task_id": "task1"
  }
}
```

- `type`：组件类型（当前仅 `quiz_card`，未来可加 `task_card`/`plan_card`）
- `data`：组件数据
- 前端按 `type` 分发渲染，未知类型忽略（安全）

## 4. 后端：`render_ui` 工具

**位置**：`deeptutor/tools/render_ui_tool.py`

**职责**：接收组件 JSON → 校验结构 → 包装为 `metadata.chart` 返回（复用现有 ChatChartCard 通道）

```python
class RenderUiTool(BaseTool):
    def get_definition(self):
        return ToolDefinition(
            name="render_ui",
            description="渲染一个教学交互组件（如练习卡片）。传入结构化组件 JSON："
                        "{\"type\":\"quiz_card\",\"data\":{question, options, answer_index, explanation, knowledge_point}}",
            parameters=[ToolParameter(name="component", type="string", description="组件 JSON", required=True)],
        )

    async def execute(self, **kwargs):
        component = json.loads(kwargs.get("component", "{}"))
        validated = _validate_component(component)  # type 校验 + 必填字段
        if validated is None:
            return ToolResult(content="组件 JSON 格式不合法", success=False)
        return ToolResult(
            content="已生成练习卡片（见上方）",
            metadata={"chart": validated},  # 复用 ChatChartCard 通道
        )
```

**注册**：`builtin/__init__.py` + always_on（教学工具）

**测试**：`tests/tools/test_render_ui_tool.py` — 合法 quiz_card 通过、缺字段失败、未知 type 失败

## 5. 前端：ChatChartCard 扩展 quiz_card

**位置**：`web/components/chat/home/ChatChartCard.tsx`

- `ChartData` union 加 `quiz_card` 类型
- 渲染：题目 + 选项按钮列表（点击 → 高亮正确/错误 + 显示 explanation）
- 本地判断：选中 `answer_index` 即对，否则错

```tsx
if (chart.type === "quiz_card") {
  return <QuizCard data={chart.data} />;
}

function QuizCard({ data }: { data: QuizCardData }) {
  const [selected, setSelected] = useState<number | null>(null);
  const answered = selected !== null;
  return (
    <div className="my-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
      <div className="mb-2 text-sm font-medium">{data.question}</div>
      <div className="space-y-1.5">
        {data.options.map((opt, idx) => {
          const isCorrect = idx === data.answer_index;
          const isSelected = idx === selected;
          const style = !answered ? "hover:bg-[var(--muted)]" :
            isCorrect ? "bg-emerald-500/10 text-emerald-600" :
            isSelected ? "bg-rose-500/10 text-rose-600" : "opacity-50";
          return (
            <button key={idx} onClick={() => setSelected(idx)} disabled={answered}
              className={`w-full rounded-lg border px-3 py-1.5 text-left text-xs ${style}`}>
              {String.fromCharCode(65 + idx)}. {opt}
              {answered && isCorrect && " ✓"}
              {answered && isSelected && !isCorrect && " ✗"}
            </button>
          );
        })}
      </div>
      {answered && data.explanation && (
        <div className="mt-2 rounded bg-[var(--muted)]/40 px-3 py-2 text-xs text-[var(--muted-foreground)]">
          {data.explanation}
        </div>
      )}
    </div>
  );
}
```

## 6. PERSONA 提示词

PERSONA 交互规范加：

```markdown
- 出练习题时用 `render_ui` 输出练习卡片（component JSON: {"type":"quiz_card","data":{question, options, answer_index, explanation, knowledge_point}}），学生点击选项即时反馈。
```

## 7. 测试

| 层 | 测试 |
|----|------|
| 后端 | `tests/tools/test_render_ui_tool.py`：合法/缺字段/未知类型 |
| 前端 | tsc + build |
| 冒烟 | Playwright：问 Coach 出道题 → 出现可点击练习卡片 → 点选项即时对错反馈 |

## 8. 明确不做

- 不引入 AG-UI/CopilotKit 框架（零新依赖）
- 不做 quiz_card 之外的类型（未来可加 task_card/plan_card，同一通道）
- 不把组件数据落库（仅当次会话渲染，学习记录仍走 write_learning_record）

## 9. 风险

- Coach 是否稳定调用 render_ui——靠 PERSONA 提示；不调用则退化为普通文本题目（无副作用）
- 组件 JSON 解析失败 → 工具返回错误，Coach 重试或改文本
- 前端未知 type 静默忽略（安全）
