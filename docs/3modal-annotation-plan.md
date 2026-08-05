# 三模态标注拓展规划文档（文本 / 图像 / 视频）

> 面向「标注星图」AI 数据标注教学平台。本文档供接力 AI 直接实施使用，包含现状、设计、改动清单、实施顺序、注意事项、验收标准。
> 前置阅读：`docs/3modal-annotation-research.md`（调研）、`docs/session-handoff-3modal.md`（项目状态）、`docs/AGENTS.md`（工程约定）。

---

## 一、背景与目标

### 目标
把平台从「仅图像标注」拓展为 **文本 / 图像 / 视频 三种数据类型的标注教学**，保持同一套 Coach 教学闭环（出题→标注→评分→反馈→推荐）。

### 竞赛支撑
- 需求方案书要求"内容专业准确性 25 分"（知识库 50+ 条）——三模态规范可显著扩充知识条目
- "功能完整性与实用性"（30 分）——三模态是功能丰富度亮点
- 技术实现合理性（25 分）——交互流程清晰、步骤引导
- 创新点：**三模态统一教学闭环 + AI 辅助标注教学**（区别于 CVAT/Doccano 等纯工具）

## 二、现状盘点（全部绑定图像）

| 层 | 现状 |
|----|------|
| 数据 | `task_bank.json` 12 任务全图像（bbox×7/class×2/judgment×1/standard×1/error_case×1），图在 `web/public/images/`（17 张） |
| 引擎 | `annotation_check.py`：bbox(IOU/F1/边缘/重叠/紧致)、classification、standard、error_case——全图像坐标 |
| 工具 | `get_annotation_task`（读 task_bank，5 种 task_type）、`annotation_check` |
| 前端 | `annotation/page.tsx` basic=Canvas 画框 / pro=LS iframe；`annotation_tool.html` 纯图像画框 |
| 规范 | `annotation-guide` skill 5 文档零三模态；`competency_tree` 有文本组（有名无实）、无视频组 |
| 知识库 | `annotation_kb` 60 篇全图像内容 |

## 三、调研结论（GitHub 成熟方案，详见 `3modal-annotation-research.md`）

- **图像**：labelImg（25k★）/ Label Studio——bbox/多边形/关键点（已有）
- **视频**：CVAT（16k★）——帧级标注 + keyframe 自动插值 + 轨迹跟踪 + AI 辅助预标注
- **文本**：Doccano（10.7k★）——文本分类 / 序列标注(NER) / seq2seq / 关系抽取；span 高亮打标签
- **关键发现**：标注**教学** Agent 无成熟现成项目 → 教学法借鉴通用 AI tutor，交互范式借鉴标注平台

## 四、总体设计：`modal × task_type` 二维矩阵

核心抽象：`annotation_check` 增加 `modal` 维度，5 种 `task_type` 跨模态复用。

| task_type | 图像 | 文本 | 视频 |
|-----------|------|------|------|
| `bbox` | ✅ 画框 | ✖ | ✅ 帧画框（CVAT 式） |
| `classification` | ✅ | ✅ 文本分类 | ✅ 行为/场景分类 |
| `judgment` | ✅ 判断题 | ✅ 判断题 | ✅ 帧序列判断 |
| `standard` | ✅ 格式合规 | ✅ 规范合规 | ✅ 轨迹/插值规范 |
| `error_case` | ✅ 改错 | ✅ 找 NER 错标 | ✅ 找轨迹断点 |

**兼容原则**：`modal` 缺省默认 `image`，现有 12 任务与评分逻辑**零破坏**。

## 五、分模态详细设计

### 5.1 文本标注（Phase 1，最快闭环）

**任务类型**（Doccano 对应）：
- `classification`：给一段文本打标签（如"该标注描述符合哪条规范：A/B/C"）
- `ner`（新增 task_type）：序列标注——高亮实体并打标签（人名/组织/地点/术语）
- `judgment`：判断标注描述对错
- `standard`：文本标注规范合规（字段完整性、标签合法性）
- `error_case`：找出文本标注中的错误（错标实体/漏标）

**数据来源**（可自建，语料易得）：
- 分类/判断/改错：标注规范知识点改写为问答（一条规范 → 一个题）
- NER：构造含实体的示例句（如"图像中车辆遮挡 50% 以上视为遮挡目标"标注术语实体）
- 规范合规：从 `annotation-guide` 提取条款

**ground truth 格式**：
```json
{
  "text": "遮挡目标处理原则：被遮挡超过50%的目标需标注",
  "entities": [{"start": 0, "end": 7, "label": "term"}, ...],
  "label": "correct"
}
```

**评分指标**：
- NER：entity 级 F1（精确匹配 start/end/label）
- 分类/判断：accuracy
- 标准：字段/标签合规率
- 改错：检出率（复用 error_case 语义）

### 5.2 视频标注（Phase 2，最重）

**任务类型**：
- `bbox`（帧级）：在指定帧上画框（标注 GT 帧的 bbox）
- `classification`：判断视频场景/行为类别
- `judgment`：判断帧序列标注是否正确
- `standard`：轨迹/插值规范合规
- `error_case`：找出轨迹断点/漏检帧

**实现策略（降级起步，逐步增强）**：
1. **v1 帧截图标注**：视频抽样 N 帧 → 对每帧做图像式画框（复用现有 Canvas 能力，改动最小）
2. **v2 帧步进标注**：播放器 + 帧步进 + 在当前帧画框 + 轨迹列表
3. **v3 keyframe 插值**（CVAT 式，可选）：关键帧标注后中间帧插值，评分校验插值正确性

**数据来源**：
- 公开数据集：MOT Challenge、YouTube-VOS（注意许可）
- 自录短视频（车辆/行人/动物，与现有图像素材同主题，衔接自然）

**ground truth 格式**：
```json
{
  "video_url": "/videos/task6.mp4",
  "frames": [{"frame": 12, "boxes": [{"x":10,"y":20,"w":50,"h":30,"label":"car"}]}],
  "duration_s": 5.2
}
```

**评分指标**：
- 帧 IOU（对该帧 GT）
- 轨迹连续性（相邻帧是否持续标注）
- 行为/场景分类 accuracy

### 5.3 图像标注（保持兼容，不动）

现有 12 任务、评分、Canvas、前端全部保留，仅新增 `modal` 维度参数。

## 六、各层改动清单

### 数据层
1. `task_bank.json`：新增 `modal` 字段（image/text/video），现有任务补 `modal: "image"`；新增文本/视频任务
2. `competency_tree.json`：文本组补全 skill 节点；新增"视频数据标注"能力组（帧标注/轨迹/插值/行为识别）
3. 视频素材：`web/public/videos/`（新目录）或独立静态目录
4. `annotation_kb`：新增 `07-文本标注/`、`08-视频标注/` 类目（各 10 篇，凑 50+ 知识条目含三模态）

### 引擎层（`annotation_check.py`）
1. 入口加 `modal` 参数（默认 image）
2. 新增 `_ner_report/_ner_dict`（文本 NER F1）
3. 新增 `_video_report/_video_dict`（帧 IOU + 轨迹连续性）
4. 现有 `_bbox_dict` 支持"帧级 bbox"（传 frame 上下文）
5. task_type 枚举扩展：`ner`

### 工具层
1. `get_annotation_task`：支持按 `modal` 过滤任务；定义文本/视频任务的 content 渲染分支
2. `annotation_check`：透传 `modal`
3. 注册处：`tools/builtin/__init__.py`（若新增工具）+ always_on（若需要）

### 前端层
1. `annotation/page.tsx`：三模态切换 Tab（文本 / 图像 / 视频），现有 basic/pro 保留为图像子模式
2. 文本标注台：`web/public/text_tool.html`（Doccano 式 span 高亮 → 选区 → 打标签 → 检查/撤销）
3. 视频标注台：`web/public/video_tool.html`（播放器 + 帧步进 + 当前帧画框 + 轨迹列表；v1 可只做帧截图）
4. 三模态共用 `render_ui` 卡片（文本任务展示简单）

### 规范层（`annotation-guide` skill）
1. `references/` 新增：`text-guide.md`（文本标注规范）、`video-guide.md`（视频标注规范）
2. `competency_tree` 对应节点挂接
3. `standards` API 自动读取新文档（目录扫描，无需改代码）

### 知识库层
1. `annotation_kb` 文本/视频类目注册进 RAG（`kb_config.json`）
2. 每篇 frontmatter 带来源（GB/T 41867、COCO、VOC、MOT 等）
3. **git 化**：`annotation_kb` + 新规范文档 `git add -f`

## 七、实施顺序与里程碑

| 阶段 | 内容 | 里程碑 |
|------|------|--------|
| **P0 兼容保障** | `modal` 参数 + 现有 12 任务补 modal=image，回归测试全绿 | 图像零破坏 |
| **P1 文本闭环** | 文本任务数据 + NER/分类评分 + 文本标注台 + 规范文档 | 文本最小闭环可用 |
| **P2 视频闭环（v1 帧截图）** | 视频素材 + 帧 bbox 评分 + 视频标注台 v1 | 视频最小闭环可用 |
| **P3 视频增强（可选）** | 帧步进/轨迹/keyframe 插值 | 交互对齐 CVAT |
| **P4 三模态统一** | 知识库扩充 + 三模态规范 + 统一教学闭环 + AI 辅助预标注 | 竞赛亮点 |

## 八、注意事项（重点，实施前必读）

### 兼容性
- **`modal` 必须默认 image**：所有现有调用不传 modal 也不受影响；`get_annotation_task` 旧 task_type 枚举不动，文本新增 `ner`、视频复用 `bbox` 加 frame 上下文
- **task_bank 旧字段不动**：新增任务才加 `modal`，别重构旧 JSON 结构
- **annotation_check 返回结构对齐**：新评分 dict 复用 `_xxx_dict` 模式（metrics + report），前端 ChatChartCard 契约不变
- **前端 annotation 页**：三模态 Tab 是新增，现有 basic/pro 按钮保持

### 数据与素材
- 文本任务**自建优先**（规范条款→题目，零版权风险）；视频素材注意许可（MOT/YouTube-VOS 有条款，或自录）
- 视频文件大：`web/public/` 静态目录是否够？大视频建议独立 `/videos/` 或对象存储；`chat_attachment_max_*` 上传限制要调
- ground truth 必须人工核对（视频 GT 帧数、文本实体边界）

### 前端与性能
- 视频标注台 v1 帧截图：用 `<video>` + canvas `drawImage` 抽帧，注意跨域/CORS
- 视频逐帧内存：抽帧间隔可配（如每 0.5s 一帧），避免长视频爆内存
- 文本 span 高亮：用浏览器 Selection API + Range，注意选区跨元素、撤销栈
- 移动端/低配设备可暂缓优化（竞赛演示用桌面）

### 竞赛要求
- 知识库 **50+ 条**必须含文本/视频规范（`annotation_kb` 扩充 + `annotation-guide` 新文档都算）
- **溯源**：每条知识/回答标注来源（议题③三态标注）
- **AI 标识**：前端统一"AI 生成内容"标识（议题⑥，05 合规 c 点）
- **不得与已发布产品雷同**：我们做**教学**（评分+反馈+个性化路径），CVAT/Doccano 是工具——差异化是教学闭环，不是又做一个标注平台
- 2-3 用户试用反馈（06 材料）：建议让评测者分别试三种标注

### 工程
- 新工具注册 **4 处**：`tools/builtin/__init__.py`（import + `BUILTIN_TOOL_TYPES` + `__all__` + `CONFIGURABLE_BUILTIN_TOOL_NAMES`）+ always_on tuple + PERSONA + 冒烟
- 循环导入：服务层 import 放函数内（懒加载）
- **`data/` 被 gitignore**：新增资产（annotation_kb、视频素材、新规范）必须 `git add -f` 提交，否则 clone 后丢失
- 测试基线：~2985 passed / 33 预存在失败（Windows/GBK/可选依赖，无关功能）；新功能回归**不得新增失败**
- 前端校验：`cd web && npx tsc --noEmit` + `next build`（**先清 `HTTP_PROXY/HTTPS_PROXY`**，本机 7890 是坏代理）
- 启动：`start_all.bat`；前端需 `DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001`（IPv6 坑）
- 规范文档路径：`annotation-guide/references/` 新增 md 即被 `/api/v1/standards` 扫描，无需改代码（**先确认扫描逻辑是否递归新文件名**）

## 九、验收标准

1. **回归**：现有 12 图像任务 + 评分 + 前端标注台全部正常，pytest 无新增失败
2. **文本闭环**：Coach 可出文本任务（分类/NER/判断/改错）→ 用户在文本标注台标注 → annotation_check 评分（NER F1/accuracy）→ 反馈 → 学习记录
3. **视频闭环**：Coach 可出视频任务（帧 bbox/分类）→ 用户在视频标注台标注 → 帧 IOU 评分 → 反馈
4. **知识库**：文本/视频规范文档 + annotation_kb 扩充完成，`/api/v1/standards` 能看到新文档，RAG 检索命中三模态内容并带来源
5. **能力树**：competency_tree 文本组补全 + 视频组新增，`graph_query` 能路由
6. **三模态统一**：同一会话内 Coach 可在三种模态间切换教学，记忆/记录正确区分 modal
7. **合规**：前端 AI 标识 + 无编造来源（verify_output 检出验证）
8. **clone 即用**：新增资产在 git，克隆后三模态可用

## 十、可复用资产与衔接（其他议题）

- **议题⑤ `route_input`**：输入分诊（"这个怎么标？"→澄清模态）——三模态教学共同基础
- **议题⑥ `verify_output`**：评分/引用输出护栏——文本/视频评分同样受检
- **议题③ 知识库**：三模态知识条目 + 溯源三标注——本轮直接落地
- **议题④ LS 联动**：LS 支持图像/文本（Doccano 式）标注，可作"专业模式"；视频 CVAT 式可另议
- **议题⑦ 总控**：三模态路由（按用户意图选模态）归总控管理
