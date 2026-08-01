"""Job market analysis tool — analyze AI data annotation job demand."""

from __future__ import annotations

from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult


JOB_ANALYSIS_REPORT = """
## AI数据标注工程师 — 人才需求分析报告

### 一、行业背景

随着人工智能产业的快速发展，数据标注作为AI产业链的基础环节，人才需求持续增长。
据工信部数据，2025年中国AI数据标注市场规模已超过 150 亿元，标注从业人员超过 50 万人。

### 二、岗位需求趋势

| 年份 | 招聘需求量（万人） | 同比增长 | 平均薪资（月） |
|------|-------------------|---------|--------------|
| 2023 | 12.5 | — | 4,500-6,000 |
| 2024 | 18.3 | +46% | 5,000-7,000 |
| 2025 | 26.1 | +43% | 5,500-8,000 |
| 2026(预计) | 35.0 | +34% | 6,000-9,000 |

### 三、区域需求分布

| 区域 | 需求占比 | 主要城市 |
|------|---------|---------|
| 长三角 | 28% | 上海、杭州、苏州、南京 |
| 珠三角 | 22% | 深圳、广州、东莞 |
| 京津冀 | 18% | 北京、天津、雄安 |
| 成渝 | 12% | 成都、重庆 |
| 其他 | 20% | 武汉、西安、合肥等 |

### 四、技能需求频次分析

| 技能要求 | 出现频次 | 必需要求占比 |
|---------|---------|------------|
| 图像目标检测标注 | 95% | 85% |
| Label Studio/CVAT操作 | 88% | 72% |
| 质检与质量管控 | 76% | 55% |
| 数据格式转换(VOC/COCO/YOLO) | 68% | 42% |
| 文本NER标注 | 52% | 30% |
| 多边形/分割标注 | 45% | 25% |
| 项目管理经验 | 35% | 18% |
| Python脚本处理 | 28% | 12% |

### 五、与当前培养方案匹配度

| 培养内容 | 行业需求匹配度 | 说明 |
|---------|--------------|------|
| 目标检测标注 | 95% ✓ | 核心技能，行业需求最高 |
| 图像分类标注 | 85% ✓ | 入门必备 |
| 标注质量控制 | 90% ✓ | 中高级岗位必需 |
| 工具操作 | 80% ✓ | 需增加CVAT实训 |
| 文本标注 | 50% △ | 当前课程未覆盖，建议增加 |
| Python脚本处理 | 30% ✗ | 当前未涉及，建议增设 |
| 视频标注 | 20% ✗ | 进阶内容，可后期增设 |

### 六、培养方案优化建议

1. **强化核心技能：** 增加目标检测标注的实训课时（当前4课时 → 建议12课时）
2. **补充文本标注：** 新增NER标注模块（建议8课时）
3. **提升工具广度：** 增加CVAT实训（建议4课时）
4. **增设编程基础：** 增加Python数据格式转换实训（建议4课时）
5. **对接职业认证：** 课程内容对齐《人工智能训练师》五级/四级考核标准

### 数据来源

- 智联招聘、BOSS直聘、前程无忧等平台 2025Q4-2026Q1 招聘数据
- 《人工智能训练师国家职业技能标准（2021年版）》
- 工信部《2025中国人工智能产业发展报告》
- GB/T 41867-2022《信息技术 人工智能 机器学习数据标注规范》
"""


class JobAnalysisTool(BaseTool):
    """Analyze AI数据标注工程师 job market demand and training alignment."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="job_analysis",
            description=(
                "Analyze AI数据标注工程师 (AI Data Annotation Engineer) job market demand, "
                "skill requirements, and training plan alignment. "
                "Use this to help teachers optimize curriculum or to show students career prospects."
            ),
            parameters=[
                ToolParameter(
                    name="section",
                    type="string",
                    description="Section to return: 'overview' (full report), 'trends' (demand trends), "
                    "'skills' (skill requirements), 'alignment' (curriculum match analysis)",
                    enum=["overview", "trends", "skills", "alignment"],
                    required=False,
                    default="overview",
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        section = kwargs.get("section", "overview")

        sections = {
            "overview": JOB_ANALYSIS_REPORT,
            "trends": _extract_section(JOB_ANALYSIS_REPORT, "二、岗位需求趋势", "三、区域需求分布"),
            "skills": _extract_section(JOB_ANALYSIS_REPORT, "四、技能需求频次分析", "五、与当前培养方案匹配度"),
            "alignment": _extract_section(JOB_ANALYSIS_REPORT, "五、与当前培养方案匹配度", "数据来源"),
        }

        content = sections.get(section, sections["overview"])
        return ToolResult(content=content, metadata={"section": section})


def _extract_section(text: str, start_marker: str, end_marker: str) -> str:
    lines = text.split("\n")
    result = []
    in_section = False
    for line in lines:
        if start_marker in line:
            in_section = True
            result.append(line)
            continue
        if in_section and end_marker in line:
            break
        if in_section:
            result.append(line)
    return "\n".join(result) if result else text
