"""Competency mapping tool — AI数据标注工程师 job competency tree."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult

COMPETENCY_PATH = Path(__file__).parent.parent.parent / "data" / "user" / "workspace" / "competency_tree.json"

DEFAULT_COMPETENCY_TREE = {
    "role": "AI数据标注工程师",
    "professional_group": "人工智能技术应用",
    "description": (
        "AI数据标注工程师是人工智能产业链中的基础岗位，负责对原始数据（图像、文本、音频、视频）"
        "进行结构化标注，为机器学习模型提供高质量训练数据。该岗位要求掌握标注工具操作、"
        "数据质量管控、标注规范设计等核心技能。"
    ),
    "standards": [
        "《人工智能训练师国家职业技能标准（2021年版）》",
        "GB/T 41867-2022 信息技术 人工智能 机器学习数据标注规范",
        "《数据标注工程》（清华大学出版社）",
    ],
    "tree": {
        "id": "root",
        "name": "AI数据标注工程师",
        "level": 1,
        "description": "核心就业岗位",
        "children": [
            {
                "id": "task-group-1",
                "name": "图像数据标注",
                "level": 2,
                "description": "对图像数据进行目标检测、分割、分类等标注",
                "children": [
                    {
                        "id": "task-1-1",
                        "name": "目标检测标注",
                        "level": 3,
                        "description": "使用矩形框标注图像中的目标物体，包括位置、大小、类别",
                        "skills": [
                            {"id": "skill-1-1-1", "name": "边界框绘制规范", "level": 4,
                             "description": "掌握最小外接矩形原则，框边距目标≤5像素"},
                            {"id": "skill-1-1-2", "name": "遮挡目标处理", "level": 4,
                             "description": "遮挡面积>50%不标注，<50%标注可见部分"},
                            {"id": "skill-1-1-3", "name": "小目标标注策略", "level": 4,
                             "description": "面积<32×32像素的目标，放大标注后还原"},
                            {"id": "skill-1-1-4", "name": "IOU计算与评测", "level": 4,
                             "description": "理解交并比概念，能计算精确率、召回率、F1分数"},
                            {"id": "skill-1-1-5", "name": "Pascal VOC格式", "level": 4,
                             "description": "掌握VOC XML标注格式的读写与转换"},
                        ],
                    },
                    {
                        "id": "task-1-2",
                        "name": "图像分类标注",
                        "level": 3,
                        "description": "对图像进行整体或局部的类别判定",
                        "skills": [
                            {"id": "skill-1-2-1", "name": "单标签分类", "level": 4,
                             "description": "每张图只属于一个类别，如猫/狗分类"},
                            {"id": "skill-1-2-2", "name": "多标签分类", "level": 4,
                             "description": "每张图可属于多个类别，如场景标注"},
                            {"id": "skill-1-2-3", "name": "细粒度分类", "level": 4,
                             "description": "区分同一大类下的子类别，如汽车品牌型号"},
                        ],
                    },
                    {
                        "id": "task-1-3",
                        "name": "语义分割标注",
                        "level": 3,
                        "description": "对图像的每个像素进行分类，实现像素级别的目标分割",
                        "skills": [
                            {"id": "skill-1-3-1", "name": "多边形轮廓描画", "level": 4,
                             "description": "沿目标边缘精确描画闭合多边形，控制点间距≤5像素"},
                            {"id": "skill-1-3-2", "name": "COCO JSON格式", "level": 4,
                             "description": "掌握COCO数据集标注格式（segmentation/bbox/category）"},
                            {"id": "skill-1-3-3", "name": "边缘细节处理", "level": 4,
                             "description": "模糊边界、毛发边缘的标注策略与容差控制"},
                        ],
                    },
                    {
                        "id": "task-1-4",
                        "name": "关键点标注",
                        "level": 3,
                        "description": "标注目标上的关键点位，如人体关节点、面部特征点",
                        "skills": [
                            {"id": "skill-1-4-1", "name": "关键点定义理解", "level": 4,
                             "description": "理解人体17点/21点模型的关节点定义"},
                            {"id": "skill-1-4-2", "name": "遮挡关键点推断", "level": 4,
                             "description": "被遮挡的关键点根据解剖结构合理推断位置"},
                        ],
                    },
                ],
            },
            {
                "id": "task-group-2",
                "name": "文本数据标注",
                "level": 2,
                "description": "对文本数据进行实体识别、关系抽取、情感分析等标注",
                "children": [
                    {
                        "id": "task-2-1",
                        "name": "命名实体识别(NER)标注",
                        "level": 3,
                        "description": "识别文本中的人名、地名、机构名等实体并标注类型",
                        "skills": [
                            {"id": "skill-2-1-1", "name": "BIO标注体系", "level": 4,
                             "description": "掌握Begin/Inside/Outside标注规范"},
                            {"id": "skill-2-1-2", "name": "嵌套实体处理", "level": 4,
                             "description": "实体嵌套情况下的标注策略（最外层优先）"},
                        ],
                    },
                    {
                        "id": "task-2-2",
                        "name": "文本分类标注",
                        "level": 3,
                        "description": "对文本进行情感极性、主题类别、意图等判定",
                        "skills": [
                            {"id": "skill-2-2-1", "name": "情感分析标注", "level": 4,
                             "description": "正/负/中性三级标注，含强度判断"},
                            {"id": "skill-2-2-2", "name": "标注一致性检验", "level": 4,
                             "description": "Kappa系数计算，≥0.6合格，≥0.8优秀"},
                        ],
                    },
                ],
            },
            {
                "id": "task-group-3",
                "name": "标注质量管理",
                "level": 2,
                "description": "保证标注数据的质量和一致性，管理标注项目进度",
                "children": [
                    {
                        "id": "task-3-1",
                        "name": "标注规范制定",
                        "level": 3,
                        "description": "编写和维护标注指导书，定义标注规则与示例",
                        "skills": [
                            {"id": "skill-3-1-1", "name": "标注指南编写", "level": 4,
                             "description": "包含规则定义、正反示例、边界case处理"},
                            {"id": "skill-3-1-2", "name": "标签体系设计", "level": 4,
                             "description": "设计层次化标签体系，避免标签歧义与重叠"},
                        ],
                    },
                    {
                        "id": "task-3-2",
                        "name": "质量抽检与反馈",
                        "level": 3,
                        "description": "按比例抽检标注结果，给出改进反馈",
                        "skills": [
                            {"id": "skill-3-2-1", "name": "抽检策略", "level": 4,
                             "description": "分层抽样（新手全检、熟手抽20%、老手抽10%）"},
                            {"id": "skill-3-2-2", "name": "常见错误分类", "level": 4,
                             "description": "漏标/多标/标错类别/定位偏移/边界模糊 五类错误"},
                            {"id": "skill-3-2-3", "name": "反馈沟通技巧", "level": 4,
                             "description": "具体指出问题+给出正确示例+说明原因，避免笼统否定"},
                        ],
                    },
                    {
                        "id": "task-3-3",
                        "name": "标注效率管理",
                        "level": 3,
                        "description": "管理标注项目进度，评估人效，优化流程",
                        "skills": [
                            {"id": "skill-3-3-1", "name": "人效评估", "level": 4,
                             "description": "标框数/小时、准确率双维度评估"},
                            {"id": "skill-3-3-2", "name": "工具选择与配置", "level": 4,
                             "description": "Label Studio/LabelImg/CVAT等工具的适用场景"},
                        ],
                    },
                ],
            },
            {
                "id": "task-group-4",
                "name": "标注工具与技术",
                "level": 2,
                "description": "熟练使用主流标注工具，了解自动化标注技术",
                "children": [
                    {
                        "id": "task-4-1",
                        "name": "标注工具操作",
                        "level": 3,
                        "description": "Label Studio、LabelImg、CVAT等工具的安装、配置与使用",
                        "skills": [
                            {"id": "skill-4-1-1", "name": "Label Studio操作", "level": 4,
                             "description": "项目创建、模板配置、任务导入导出、评审流程"},
                            {"id": "skill-4-1-2", "name": "CVAT操作", "level": 4,
                             "description": "团队协作标注、自动标注辅助、格式转换"},
                            {"id": "skill-4-1-3", "name": "数据格式转换", "level": 4,
                             "description": "COCO↔VOC↔YOLO↔LabelMe格式互转"},
                        ],
                    },
                    {
                        "id": "task-4-2",
                        "name": "自动标注技术",
                        "level": 3,
                        "description": "了解预标注、辅助标注、主动学习等自动化方法",
                        "skills": [
                            {"id": "skill-4-2-1", "name": "预标注原理", "level": 4,
                             "description": "了解模型预标注→人工修正的半自动流程"},
                            {"id": "skill-4-2-2", "name": "主动学习策略", "level": 4,
                             "description": "不确定性采样、多样性采样等减少标注量的策略"},
                        ],
                    },
                ],
            },
        ],
    },
}


def _load_competency_tree() -> dict:
    if COMPETENCY_PATH.exists():
        return json.loads(COMPETENCY_PATH.read_text(encoding="utf-8"))
    return DEFAULT_COMPETENCY_TREE


def _format_tree_node(node: dict, indent: int = 0) -> str:
    """Recursively format a tree node and its children into markdown."""
    prefix = "  " * indent
    markers = {1: "##", 2: "###", 3: "####", 4: "-", 5: "  -"}
    marker = markers.get(node.get("level", 1), "-")

    if node.get("level", 1) <= 3:
        lines = [f"{prefix}{marker} {node['name']}", f"{prefix}{node.get('description', '')}"]
    else:
        lines = [f"{prefix}{marker} **{node['name']}**: {node.get('description', '')}"]

    if "children" in node:
        for child in node["children"]:
            lines.append(_format_tree_node(child, indent + 1))
    if "skills" in node:
        for skill in node["skills"]:
            lines.append(_format_tree_node(skill, indent + 1))
    return "\n".join(lines)


class CompetencyMapTool(BaseTool):
    """Query or visualize the AI数据标注工程师 job competency tree."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="competency_map",
            description=(
                "Query the AI数据标注工程师 (AI Data Annotation Engineer) job competency tree. "
                "Returns a structured skill map showing: role → task groups → tasks → skills → knowledge points. "
                "Use this to show students what skills they need to master, "
                "or to help teachers design curriculum aligned with job requirements."
            ),
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="What to return: 'overview' (role intro + top-level tree), "
                    "'full_tree' (complete tree), 'node' (specific node by id)",
                    enum=["overview", "full_tree", "node"],
                    required=False,
                    default="overview",
                ),
                ToolParameter(
                    name="node_id",
                    type="string",
                    description="Node ID to query when action='node'. E.g., 'task-1-1' for 目标检测标注.",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        data = _load_competency_tree()
        action = kwargs.get("action", "overview")
        node_id = kwargs.get("node_id")

        if action == "overview":
            role = data["role"]
            group = data["professional_group"]
            desc = data["description"]
            standards = "\n".join(f"- {s}" for s in data["standards"])
            root = data["tree"]
            top_level = "\n".join(
                f"- **{c['name']}**: {c['description']}" for c in root.get("children", [])
            )

            content = (
                f"## {role} — {group}\n\n{desc}\n\n"
                f"### 参考标准\n{standards}\n\n"
                f"### 核心能力领域\n{top_level}\n\n"
                f"能力图谱共包含 **{self._count_nodes(data['tree'])}** 个学习节点"
                f"（{self._count_tasks(data['tree'])} 个任务、{self._count_skills(data['tree'])} 个技能点）。\n\n"
                f"使用 `competency_map action=full_tree` 查看完整图谱，"
                f"使用 `competency_map action=node node_id=xxx` 查看具体节点。"
            )

        elif action == "full_tree":
            content = f"## {data['role']} — 完整能力图谱\n\n"
            content += _format_tree_node(data["tree"])
            content += (
                f"\n\n---\n图谱统计：{self._count_nodes(data['tree'])} 个节点"
                f"（{self._count_tasks(data['tree'])} 个任务、{self._count_skills(data['tree'])} 个技能点）"
            )

        elif action == "node":
            content = self._find_and_format_node(data["tree"], node_id) if node_id else "请指定 node_id"

        else:
            return ToolResult(content=f"Unknown action: {action}", success=False)

        return ToolResult(
            content=content,
            metadata={
                "action": action,
                "node_id": node_id,
                "total_nodes": self._count_nodes(data["tree"]),
                "total_tasks": self._count_tasks(data["tree"]),
                "total_skills": self._count_skills(data["tree"]),
            },
        )

    def _count_nodes(self, node: dict) -> int:
        count = 1
        for child in node.get("children", []):
            count += self._count_nodes(child)
        for skill in node.get("skills", []):
            count += self._count_nodes(skill)
        return count

    def _count_tasks(self, node: dict) -> int:
        count = 1 if node.get("level") == 3 else 0
        for child in node.get("children", []):
            count += self._count_tasks(child)
        return count

    def _count_skills(self, node: dict) -> int:
        count = len(node.get("skills", []))
        for child in node.get("children", []):
            count += self._count_skills(child)
        return count

    def _find_and_format_node(self, node: dict, target_id: str) -> str:
        if node.get("id") == target_id:
            return _format_tree_node(node)

        for child in node.get("children", []):
            result = self._find_and_format_node(child, target_id)
            if result:
                return result
        for skill in node.get("skills", []):
            result = self._find_and_format_node(skill, target_id)
            if result:
                return result

        return f"未找到节点: {target_id}"
