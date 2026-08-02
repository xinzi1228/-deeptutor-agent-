# 对话内可视化设计文档（Chat Visualization）

> 关联: 竞赛文件「标注星图_团队分工与周报模板_v5.5.docx」模块⑤学习报告插件
> 借鉴: `code_execution+matplotlib`（本地 DESIGN.md 已设计）、`feynman-tutor` 可视化转交、`antvis/chart-visualization-skills`、`aetherviz-master`（均已分析）
> 状态: 设计稿。改代码前先对照本文件逐项验收。

---

## 1. 背景与目标

**问题**: 对话输出全是纯文字，不满足竞赛"学习报告插件（E）JS渲染：进度条/成绩单/薄弱项图表"的可视化要求。

**目标**: 在对话流内展示 4 类图表卡片——练习成绩单、能力雷达、学习进度、知识图谱风险链——全部由**确定性数据**驱动，LLM 只负责文字，不负责画图。

**设计原则**:
1. **数据确定性**: 图表数据由工具计算产生（评测分数/能力分数/进度/图谱），LLM 不参与画图（防止画错）。
2. **文字+图表并存**: 保留原有文字反馈，图表作为增强卡片跟在文字后面（不取代）。
3. **混合技术**: 成绩单用 matplotlib 图片（可截图进 PPT、跨端兼容），雷达/图谱用 Chart.js 交互卡（可悬停）。
4. **最小可视化纪律**（tutor-visualize 借鉴）: 只画当前需要的，不过度可视化。

---

## 2. 架构概览

```
工具层                         对话流                         前端渲染
┌────────────────┐   ┌──────────────────────┐   ┌────────────────────┐
│ annotation_check │   │ ToolResult.metadata   │   │ ChatMessages       │
│ competency_map   │──▶│   + chart: {...}      │──▶│ 检测 chart 字段     │
│ finalize_diagnosis│  │ (确定性结构化数据)    │   │ → ChartCard 组件    │
│ graph_query      │   └──────────────────────┘   │  · matplotlib图     │
└────────────────┘                                 │  · Chart.js 交互    │
                                                    └────────────────────┘
```

**两种图表形态**:
| 形态 | 技术 | 场景 | 借鉴来源 |
|------|------|------|---------|
| **图片卡** | `code_execution` + matplotlib 生成 PNG → `/api/outputs` | 练习成绩单（F1/Precision/Recall） | 本地 DESIGN.md L256 + phase0 spec |
| **交互卡** | 工具返回 `chart` JSON → 前端 Chart.js | 能力雷达 / 学习进度 / 图谱 | `VisualizationViewer` ChartJsRenderer |

---

## 3. 四个图表详细设计

### 3.1 练习成绩单（matplotlib 图片卡）

**触发**: `annotation_check` 评测完成后。

**数据**: F1 / Precision / Recall + 逐框反馈（对/多画/漏标）。

**图表**: matplotlib 生成成绩单图（柱状或仪表），尺寸 ~700×300：
- F1 大数字 + 分数条（≥0.7 绿 / <0.7 红）
- Precision / Recall 两个副指标柱
- 底部逐框反馈列表

**展示**: 工具生成 PNG → `/api/outputs/.../scorecard.png` → 对话 markdown 插入图片 → 前端 `<img>` 渲染（RichMarkdownRenderer 已支持图片）。

**对应竞赛**: 模块⑤"成绩单"。

### 3.2 能力雷达（Chart.js 交互卡）

**触发**: `competency_map` 或诊断后、学生问"我能力怎么样"。

**数据**: 五维能力分数（框精度/标签准确/完整性/一致性/知识掌握）。

**图表**: Chart.js Radar（复用 `RadarChart.tsx` 逻辑，组件化进对话）。

**展示**: 工具返回 `metadata.chart = {type:"radar", data:{labels, values}}` → 前端 `ChatChartCard` 检测 → 渲染交互雷达。

**对应竞赛**: 模块⑤"薄弱项图表" + 能力图谱可视化。

### 3.3 学习进度（Chart.js 交互卡）

**触发**: `finalize_diagnosis` 建课后 / 学生问"我学到哪了"。

**数据**: 任务完成数 / 模块进度 / 计划 vs 实际。

**图表**: 进度条 + 计划vs实际对比（bar 或 progress）。

**展示**: `metadata.chart = {type:"progress", data:{completed, total, modules:[...]}}` → 前端渲染。

**对应竞赛**: 创新方向"学习计划可视化对比（计划vs实际）"。

### 3.4 知识图谱风险链（Chart.js / cytoscape 交互卡）

**触发**: `graph_query(query_type="risk_path")` 之后。

**数据**: 技能依赖 + 掌握/挣扎状态 + 风险链。

**图表**: 依赖图（cytoscape 已装）或层次图。

**展示**: `metadata.chart = {type:"graph", data:{nodes, edges, risky:[]}}` → 前端渲染（cytoscape 或简化 Chart.js）。

**对应竞赛**: S2 职业岗位能力图谱 + 思维导图可视化。

---

## 4. 数据契约（工具 → 前端）

统一 `metadata.chart` 契约：

```json
{
  "chart": {
    "type": "radar" | "progress" | "graph" | "scorecard",
    "data": { ... 类型相关 ... },
    "title": "可选标题"
  }
}
```

- **scorecard**: 走 matplotlib 图片（`metadata.image` 指向 PNG URL），不走 chart JSON
- **radar**: `{labels: [5维], values: [0-100]}`
- **progress**: `{completed, total, modules: [{name, done, total}]}`
- **graph**: `{nodes: [{id,label,status}], edges: [{source,target}], risky: [id]}`

---

## 5. 前端实现要点

### 5.1 `ChatChartCard` 组件（新增）

位置: `web/components/chat/home/`（`AssistantMessage` 分支）。

职责:
- 检测消息元数据中的 `chart` 字段 → 按 type 分发渲染
- `scorecard`: 渲染 `<img>`（matplotlib PNG）
- `radar`: 复用/提取 Chart.js Radar 逻辑
- `progress`: 进度条 + bar
- `graph`: cytoscape 依赖图

### 5.2 检测链路

工具 `ToolResult.metadata.chart` → StreamBus tool_result 事件 → `metadata.tool_metadata` → 前端消息对象 → `AssistantMessage` 渲染时检查。

现有 `extractStreamedArtifacts`（`InlineFileCard.tsx:48-77`）已处理 artifacts，chart 走类似通道。

### 5.3 图片渲染

matplotlib PNG 经 `/api/outputs` 公开 → markdown `![](url)` → RichMarkdownRenderer 已支持（`RichMarkdownRenderer.tsx:651-660`）。

---

## 6. 工具层实现要点

### 6.1 `annotation_check`（成绩单图片）

- 评测后调 `code_execution`（或直接 matplotlib）生成 scorecard PNG
- PNG 写入 workspace 输出目录 → `collect_public_artifacts` → 返回 URL
- ToolResult.content 追加 `![成绩单](url)`

### 6.2 `competency_map` / `finalize_diagnosis` / `graph_query`

- 计算确定性数据 → 填入 `metadata.chart`
- 不改 content（文字照旧），chart 作为附加元数据

---

## 7. 错误处理与降级

| 场景 | 处理 |
|------|------|
| matplotlib 不可用 / 生成失败 | 降级为纯文字成绩单（现状），不阻塞 |
| chart JSON 前端渲染失败 | 降级为文字 + 数据表格 |
| 无图谱数据 | graph 卡显示空态"先完成诊断" |
| 图片 URL 失效 | markdown 图片 alt 文本兜底 |

---

## 8. 测试策略

| 测试 | 验证点 |
|------|--------|
| 工具 chart 契约 | annotation_check 返回 scorecard 图；competency 返回 radar chart JSON |
| 前端渲染 | ChartCard 对 4 种 type 正确渲染 |
| 降级路径 | matplotlib 失败 → 文字成绩单；chart 损坏 → 表格 |
| 图片产物 | scorecard.png 生成 + /api/outputs 可访问 |
| 回归 | 对话仍正常（图表不破坏现有文字反馈） |

---

## 9. 与竞赛对标

| 竞赛要求 | 本设计 |
|---------|--------|
| 模块⑤ 学习报告插件 JS渲染：进度条/成绩单/薄弱项图表 | ✅ 4 类图表卡：成绩单(matplotlib)/进度条(Chart.js)/雷达+图谱(交互) |
| 创新方向: 学习计划可视化对比(计划vs实际) | ✅ progress 卡含计划vs实际 |
| S2 岗位能力图谱 + 思维导图可视化 | ✅ 能力雷达 + 图谱风险链 |
| "全部在星辰对话界面完成，不额外开发前端" | ✅ 不新建页面，图表内嵌对话流 |

---

## 10. 明确不做（YAGNI）

- ~~对话内 SVG/Three.js 3D 可视化~~（2D 足够，aetherviz 重型方案暂缓）
- ~~ECharts/d3 引入~~（Chart.js 已满足）
- ~~图表点击跳转新页面~~（对话内内嵌即可）
- ~~LLM 生成图表代码~~（数据确定性优先，防止画错）
