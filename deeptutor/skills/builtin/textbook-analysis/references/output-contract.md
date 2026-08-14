# 教材分析候选输出契约

向 `textbook_candidate` 的 `candidates_json` 传入 JSON 数组。每项包含：

```json
{
  "kind": "term",
  "title": "边界框",
  "content": "用于圈定图像中目标范围的矩形标注。",
  "source_pages": [12],
  "claim_scope": "background"
}
```

`kind` 只能是：`term`、`knowledge_point`、`procedure`、`safety_rule`、`summary`、`candidate_question`、`conflict`。

`claim_scope` 只能是：`mandatory_requirement`、`recommendation`、`example_threshold`、`background`。候选题可额外提供 `options`、`answer` 和 `explanation`，但答案与解释仍必须能回到 `source_pages`。

冲突项必须同时引用教材来源和至少一个受控标准来源；系统只登记冲突，不让 Agent 决定谁覆盖谁。
