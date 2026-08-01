---
name: annotation-guide
description: 数据标注知识速查手册。标注类型、质量指标、最佳实践、工具使用。当用户询问标注技术、质量标准、标注评测或想学习如何正确标注时使用。
---

# 数据标注指南

快速参考手册。详细内容在 `references/` 按需加载。

## 标注类型速览

| 类型 | 关键指标 | 对应任务 | 详细参考 |
|------|---------|---------|---------|
| 目标检测 (Bounding Box) | IOU ≥ 0.5 | task1-4, 6-8 | `references/bbox-guide.md` |
| 图像分类 (Classification) | Accuracy, F1 | task5, 9 | `references/classification-guide.md` |
| 多边形分割 (Segmentation) | Pixel IOU | — | `references/bbox-guide.md` |
| 关键点标注 (Keypoint) | OKS | — | `references/bbox-guide.md` |
| 文本NER标注 | F1, Kappa | — | 待扩展 |
| 视频标注 | 跟踪精度 | — | 待扩展 |

## 质量指标速查

| 指标 | 公式 | 合格线 | 优秀线 | 详细参考 |
|------|------|--------|--------|---------|
| IOU | 交集/并集 | ≥ 0.5 | ≥ 0.7 | `references/quality-metrics.md` |
| Precision | TP/(TP+FP) | ≥ 90% | ≥ 95% | `references/quality-metrics.md` |
| Recall | TP/(TP+FN) | ≥ 85% | ≥ 93% | `references/quality-metrics.md` |
| F1 | 2×P×R/(P+R) | ≥ 0.85 | ≥ 0.93 | `references/quality-metrics.md` |
| Cohen's Kappa | — | ≥ 0.6 | ≥ 0.8 | `references/quality-metrics.md` |

## 何时调用 annotation_check

- 用户完成了标注任务需要评测时
- 需要计算 IOU / F1 / Precision / Recall 时
- 需要逐框定量反馈时

参数: `predictions` (JSON数组), `ground_truth` (JSON数组), `task_type` ("bbox" | "classification")

## 常见标注陷阱

| 陷阱 | 解决方法 | 对应 rag 关键词 | 详细参考 |
|------|---------|---------------|---------|
| 标签不一致 | 定期校准会议 | "标注不一致案例" | `references/best-practices.md` |
| 边界模糊 | 写死规则(如"框包含尾巴") | "边界模糊处理" | `references/best-practices.md` |
| 标注疲劳 | 45-60分休息，轮换任务类型 | "标注疲劳错误" | `references/best-practices.md` |
| 类别不平衡 | 评审时过采稀类 | — | `references/best-practices.md` |
| 确证偏见 | 标注员轮换数据源 | — | `references/best-practices.md` |
| 标准漂移 | 试点后锁定，版本控制 | "标注标准漂移" | `references/best-practices.md` |

## References 按需加载

- `references/bbox-guide.md` — 目标检测标注详解 (对应 task1-8, Phase1 Step1 + Phase2 Step5)
- `references/classification-guide.md` — 分类标注详解 (对应 task5,9)
- `references/quality-metrics.md` — IOU/F1/Kappa 完整说明 (Phase1 Step1 + Phase2 Step5)
- `references/best-practices.md` — 指南设计+标注工作流+陷阱 (Phase1 Step1)
- `references/tool-usage.md` — annotation_check 等工具的使用时机 (Phase2 Step4)
