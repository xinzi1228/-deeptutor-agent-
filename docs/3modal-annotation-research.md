# 三模态标注拓展：现状梳理 + GitHub 成熟方案调研（2026-08-05）

> 用途：支撑「文本/图像/视频 三模态标注」规划文档。调研对象：标注平台（CVAT/Doccano/labelImg）+ 教育 Agent（universal-diagnostic-tutor 等通用教学法）。

---

## 一、现状：全套实现绑定「图像」

### 数据层
- `task_bank.json`：12 任务**全图像**（bbox×7、classification×2、judgment×1、standard×1、error_case×1），`image_url` → `web/public/images/`（17 张图）
- `competency_tree.json`：4 能力组 = 图像标注 / **文本标注（已有节点，有名无实）** / 质量管控 / 工具技术；**无视频标注节点**

### 引擎层（`annotation_check.py`）
- 评分能力：`bbox`（IOU/F1/边缘/重叠/紧致）、`classification`、`standard`（字段/标签/坐标范围）、`error_case`——全基于图像 bbox 坐标

### 工具层
- `get_annotation_task`：读 task_bank，5 种 task_type（全图像格式）
- `annotation_check`：按 task_type 评分

### 前端层
- `annotation/page.tsx`：basic = Canvas 画框（`annotation_tool.html`），pro = Label Studio iframe
- `annotation_tool.html`：纯图像 Canvas 画框（画框→选标签→检查/撤销/清空）

### 规范层
- `annotation-guide` skill 5 文档：**零三模态**（bbox/分类/质量指标/工具）

## 二、GitHub 成熟方案调研

### 标注平台（三模态各自的交互范式）

| 模态 | 平台 | 核心能力 | 可借鉴交互范式 |
|------|------|---------|----------------|
| 图像 | labelImg（25k★，并入 LS） | bbox/多边形/关键点 | 已有（Canvas 画框） |
| 视频 | **CVAT**（16k★） | **帧级标注 + keyframe 自动插值 + 轨迹跟踪** + 图像/视频/3D 统一 + **AI 辅助标注**（连 ML 模型预标注） | 帧步进导航、关键帧插值、轨迹连续性 |
| 文本 | **Doccano**（10.7k★） | **文本分类 / 序列标注(NER) / seq2seq / 关系抽取**；span 高亮+打标签 | 选区高亮→标签（替代画框） |

### 关键发现：标注教学 Agent 是空白

- 搜"data annotation training agent"等：**几乎无成熟项目**（唯一命中 0★ 不成熟）
- 双刃：⚠️ 无现成教学法可借鉴 → ✅ 竞赛要求"**不得与已发布产品雷同**"，我们是赛道开拓者
- **结论**：教学法借鉴通用 AI tutor（universal-diagnostic-tutor/feynman-tutor），交互范式借鉴标注平台（CVAT/Doccano）

## 三、可复用抽象：`modal × task_type` 矩阵

`task_type` 5 类型天然跨模态（评分引擎只需加 `modal` 维度）：

| task_type | 图像 | 文本 | 视频 |
|-----------|------|------|------|
| `bbox` | ✅ 画框 | ✖ | ✅ 帧画框（CVAT 式） |
| `classification` | ✅ | ✅ 文本分类（Doccano） | ✅ 行为/场景分类 |
| `judgment` | ✅ 判断题 | ✅ 判断题 | ✅ 帧序列判断 |
| `standard` | ✅ 格式合规 | ✅ 标注规范合规 | ✅ 轨迹/插值规范 |
| `error_case` | ✅ 改错 | ✅ 找 NER 错标 | ✅ 找轨迹断点 |

## 四、三模态评分设计参考

| 模态 | 评分指标 | 复用点 |
|------|---------|--------|
| 文本 | NER F1（实体级）、分类准确率、情感判定、关系抽取准确率 | classification 已实现可复用 |
| 视频 | 帧 IOU（对 GT 帧）、轨迹/插值连续性、行为标签匹配 | bbox 是帧版复用 |
| 图像 | IOU/F1/边缘/重叠（已实现） | 已有 |

## 五、规划文档建议切入点

1. **抽象优先**：先定 `modal(文本/图像/视频) × task_type(5 种)` 二维矩阵，再定数据/评分/前端
2. **最小闭环顺序**：文本（competency 已有节点 + classification 复用）→ 视频（最重：帧处理+插值，可先用"视频帧截图标注"降级起步）
3. **前端**：文本标注台（Doccano 式 span 高亮）、视频标注台（CVAT 式帧步进+画框）、图像（已有 Canvas）
4. **数据**：文本任务可自建（分类/NER 语料易得）；视频需找素材（公开数据集/自录）
5. **创新点**（竞赛加分）：三模态统一教学闭环（同一 Coach 教三种标注）+ AI 辅助标注教学（CVAT 式预标注）
