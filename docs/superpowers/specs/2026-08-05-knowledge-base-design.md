# 议题③ 设计：知识库 / 检索 / 数据收集

> 竞赛评分点：需求方案书「内容专业准确性 25 分」——知识库含 **50 条以上专业内容且标注来源**；关键知识点标注依据来源；嵌入专业领域知识（RAG 知识库/提示词模板/校验规则）。

## 1. 现状梳理（现在大模型输出靠什么）

| 路 | 内容 | 状态 |
|----|------|------|
| PERSONA 内置 | Coach 人设内置标注规范知识 | ✅ |
| standards 规范库 | `annotation-guide/references` 5 篇 → `/api/v1/standards` 引用溯源 | ✅ |
| task_bank / competency_tree / graph_query | 出题 + 能力树 + 学习者图谱 | ✅ |
| **RAG 向量库** | `services/rag` 全套基建 | ⚠️ **已就绪但 `knowledge_bases` 空，未接入** |

**素材盘点**：`data/user/workspace/annotation_kb/` 已有 **60 篇知识文档**（6 大类 × 10：基础知识/行业标准/工具操作/质量管控/常见错误/项目管理），但**没进 git、没注册为 RAG 源**。

## 2. RAG 基础设施能力（已核实，无需升级）

- **Hybrid 检索**：BM25（关键词）+ 向量 QueryFusion，默认 `HYBRID_PROFILE`，BM25 缺失自动 fallback
- **多查询检索**：`SmartRetriever` 生成查询变体 → 融合 → 聚合
- **多 provider**：llamaindex / lightrag

**结论：RAG 引擎不需要升级**（已是现代 hybrid + fusion）。缺的是"接入 + 增强"：数据注册、相关性校验、范围限定、溯源。**明确不做**：换框架、Graph RAG 全量图、分布式向量库/语义缓存。

## 3. 调研借鉴（GitHub 成熟方案）

| 来源 | 核心机制 | 融入点 |
|------|---------|--------|
| universal-examprep-skill（263★） | **溯源三标注**：From your materials（可溯源）/ AI-supplemented（可能与标准不同）/ AI-generated（非教材）；"知识库不支撑就明说"；按需 on-demand vs 全量构建 | 检索结果三态标注；轻量按需检索 |
| towardsai/ai-tutor-app | 双路检索（Chroma 向量 + Graph RAG）；**kb_shell 受限检索壳**（agent 用 rg/grep 精确检索知识库，强校验路径/禁 shell 拼接） | `kb_search` 精确检索工具 |
| lumen | **course-scoped RAG**（只检索当前模块 KB） | 按学习阶段限定检索类别 |
| CRAG（awesome-llm-apps） | 检索后**相关性评分** → 低相关改写查询 / 明说"知识库无此内容" | 相关性校验（防幻觉） |
| RAGFlow | 父子 chunk（小 chunk 检索 / 大 chunk 上下文） | 可选增强 |

## 4. 设计

### 4.1 知识库构建
- `annotation_kb` 60 篇注册为 RAG 知识库（`kb_config.json` 的 `knowledge_bases`，provider=llamaindex，profile=hybrid）
- 每篇 frontmatter 带**来源**（GB/T 41867、COCO/Pascal VOC 规范等）
- **纳入 git**（`git add -f`）→ clone 即用、评审可查
- 前端新增知识库页（展示 60 条 + 来源，佐证"50+ 条专业内容"）

### 4.2 三路检索
```
用户提问 → ① 精确：kb_search 工具（standards 规范库定位 + annotation_kb grep/章节定位）
        → ② 向量：annotation_kb 语义检索（RAG hybrid，SmartRetriever 多查询）
        → ③ 图谱：graph_query + competency_tree（个性化路由，新技能前置检查）
```
- `kb_search` 借鉴 kb_shell 安全约束（路径限定知识库目录、只读命令白名单）
- **范围限定**（course-scoped）：按当前学习阶段/任务限定检索类别（学 bbox 只检"基础知识+标准+错误"类）

### 4.3 相关性校验（CRAG，防幻觉核心）
- 检索后 LLM 评分相关性 → 低相关：改写查询重试 / 明说"知识库无此内容"，不硬凑
- 与议题⑥ `verify_output.evidence_missing` 联动：断言必须有来源，无则检出

### 4.4 溯源三标注（竞赛评分点）
- 检索结果/回答强制三态标注：
  - **可溯源**：`依据〔规范: 文档§章节〕`（standards 引用）
  - **AI 补充**：标注"通用教学建议，非标准条款"
  - **无依据**：明说"知识库未收录此内容"

### 4.5 数据收集规划
| 类型 | 来源 | 用途 |
|------|------|------|
| 知识条目 | annotation_kb 60 篇（带来源） | 教学依据库 |
| 学习数据 | records / decisions / trace-log（已有） | 个性化路径 |
| 输入质量 | route_input 分布（议题⑤） | 优化澄清 |
| 输出质量 | QUALITY_RUBRIC 打分（议题⑥） | 改进 PERSONA |
| 用户反馈 | 2-3 用户测试（竞赛要求） | 06 材料 |

## 5. 实现与测试

- 注册知识库：`kb_config.json` + 每篇 frontmatter 来源
- 新工具：`kb_search`（注册 4 处）
- 测试：`tests/services/rag/test_annotation_kb.py`（检索命中、范围限定、相关性低时明说）
- 冒烟：问"遮挡目标怎么标"→ 命中 annotation_kb「遮挡目标处理」+ 来源标注

## 6. 衔接

- 议题⑥ `verify_output.evidence_missing` 依赖本节来源标注
- 议题⑦ 总控负责路由到哪路检索（精确/向量/图谱）
