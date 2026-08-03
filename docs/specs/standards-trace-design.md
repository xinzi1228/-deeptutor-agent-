# 引用溯源（标注规范库 + 对话内自动检测）设计

> 状态: 设计已获用户批准
> 日期: 2026-08-03

---

## 1. 背景与目标

Coach 在教学对话中会引用标注规范（PERSONA 规则："引用标准时注明来源，如 GB/T 41867-2022 §6.1"），规范原文存在 `deeptutor/skills/builtin/annotation-guide/references/*.md`。但目前：
- 对话中这些引用是**纯文本**，不可点击查看原文
- 无"规范库"页面集中查看规范文档

**目标**：
1. 后端暴露规范文档目录（文档 + 章节标题）
2. 前端「标注规范库」页面：列文档/章节，点开看全文
3. 对话内自动检测文档名/标准号关键词 → 高亮可点击 → 打开对应文档

**来源**：差距分析 §十二 P0 引用溯源可点击。机制基础：RichMarkdownRenderer 已有 `title="citation"` 引用锚点处理（`findCitationAnchor`），本设计在其上增加"规范链接"类型。

## 2. 设计决策汇总

| # | 维度 | 决策 |
|---|------|------|
| 1 | 后端 | `GET /api/v1/standards` — 从 annotation-guide skill references 读取文档 + 章节 |
| 2 | 前端库页 | 侧边栏「标注规范」入口 → 规范库页（文档卡片 + 章节导航 + 全文） |
| 3 | 对话检测 | RichMarkdownRenderer 检测 `〔规范: 文档名§章节〕` / `GB/T xxx` / 文档名 → 可点击 |
| 4 | 打开方式 | 点击 → 弹窗（Dialog）显示该文档章节原文 |
| 5 | Coach 无需改 | 检测是前端的，文档名/标准号自动匹配 |

## 3. 后端 `GET /api/v1/standards`

**位置**：新 `deeptutor/api/routers/standards.py`（挂 `/api/v1`，auth 依赖与其他一致）

**实现**：
```python
STANDARDS_DIR = <path to deeptutor/skills/builtin/annotation-guide/references>

@router.get("/standards")
async def standards() -> dict[str, Any]:
    """标注规范文档目录：从 annotation-guide skill references 读取。"""
    docs = []
    for md in sorted(STANDARDS_DIR.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        sections = _extract_sections(text)  # ## / ### 标题
        title = _derive_title(md, text)     # 文件首 # 标题 或文件名
        docs.append({"id": md.stem, "title": title, "sections": sections, "content": text})
    return {"standards": docs}
```

- `_extract_sections`：正则找 `^##\s+(.+)` 行，返回标题列表
- `_derive_title`：文件内首个 `# 标题`，否则用文件名可读化（bbox-guide → 目标检测标注）
- content 全量返回（文档小，教学场景够；若担心体积可加 `?content=false` 参数，先全量简单）

**测试**：`tests/api/test_standards.py` — 返回文档数 > 0、每文档有 id/title/sections、bbox-guide 含预期章节（边界框绘制）。

## 4. 前端「标注规范库」页面

**入口**：侧边栏 Secondary NAV 加「标注规范」（与 记忆/设置 同级）
**路由**：`web/app/(utility)/standards/page.tsx`
**组件**：
- 文档卡片列表：`id` + `title` + 章节数
- 点开文档 → 展开全文（或独立视图），章节可锚点跳转
- 复用现有 `RichMarkdownRenderer` 渲染 markdown（规范文档是 .md）

**数据**：`web/lib/standards-api.ts` 加 `getStandards()`（fetch `/api/v1/standards`）

## 5. 对话内自动检测（RichMarkdownRenderer 增强）

**目标格式**：Coach 输出规范引用时，前端自动识别三类：
1. `〔规范: bbox-guide §边界框绘制〕` — 显式结构化
2. `GB/T 41867-2022` / `GB/T xxx` — 标准号（若规范库文档含该标准则链接）
3. 规范文档名（bbox-guide / 遮挡目标处理 等，在 references 文档标题/章节中匹配）

**实现**：在 `RichMarkdownRenderer` 的处理流程中，对纯文本段落加一步"规范链接检测"：
- 把匹配到的 `〔规范: ...〕` 或 `GB/T 数字` 或文档名 → 渲染为 `<StandardLink docId={...} section={...}>`
- 点击 → 打开 `StandardDialog`（复用 common Dialog 模式）显示该文档/章节原文

**简化决策**：优先支持 `〔规范: 文档名§章节〕` 显式格式（Coach 输出它时触发），`GB/T` 标准号匹配放第二阶段（规范库文档实际不含 GB/T 文本——探索发现 references 是自写规范，无标准号引用）。**即：对话检测只认 `〔规范: ...〕` 标记**，避免误匹配。

**阶段**：
- Phase 1（本次）：规范库页 + `/standards` 端点
- Phase 2（本次）：对话 `〔规范: ...〕` 检测 → 可点击弹窗
- Phase 3（可选）：Coach 提示词补充"输出规范引用用〔规范: 文档名§章节〕格式"

## 6. 测试

| 层 | 测试 |
|----|------|
| 后端 | `tests/api/test_standards.py`：文档数、章节提取、title 派生 |
| 前端 | tsc + build；`standards-api` 类型 |
| 冒烟 | Playwright：规范库页显示文档 → 点开看全文；对话含 `〔规范: bbox-guide§边界框绘制〕` 可点击 → 弹窗 |

## 7. 明确不做

- 不做知识库入库（规范文档留在 skill references，不复制到 kb）
- 不做 GB/T 标准号匹配（规范文档无标准号，Phase 2 只认显式标记）
- 不做 Coach 提示词强制（Phase 3 可选，本次不动 Coach）

## 8. 风险

- 文档全量返回 content 可能稍大（references 约 5 个文件，每个 <5KB，可接受）
- `〔规范: ...〕` 标记若 Coach 不输出则检测不触发（退化为纯文本，无副作用）
