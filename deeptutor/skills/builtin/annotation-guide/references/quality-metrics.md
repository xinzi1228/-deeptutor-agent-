# 质量指标详解

> 适用阶段: Phase1 理论 Step1 (教学时引用) / Phase2 实践 Step5 (反馈时解释分数)

## IOU (交并比) — 目标检测

```
IOU = 交集面积 / 并集面积
```

| IOU | 含义 |
|-----|------|
| ≥ 0.7 | 高质量标注 |
| ≥ 0.5 | 基本合格（常用阈值） |
| < 0.3 | 需要大幅改进 |

**直观理解:** 两个框重叠越多，IOU 越大。1.0 = 完全重合，0 = 完全不重合。

## Precision & Recall — 分类/检测

```
Precision = TP / (TP + FP)   — "标出的框中，有多少是对的？"
Recall    = TP / (TP + FN)   — "该标的框里，实际标了多少？"

TP = 正确匹配的框
FP = 多标的框（不该标但标了）
FN = 漏标的框（该标但没标）
```

**教学类比:** 警察抓小偷。Precision = 抓的人中多少是真小偷。Recall = 所有小偷中抓到了多少。

## F1 Score — 综合指标

```
F1 = 2 × (Precision × Recall) / (Precision + Recall)
```

0 到 1 的调和平均数。当 Precision 和 Recall 差距大时，F1 更接近较小的那个。

## 标注者间一致性 (Inter-Annotator Agreement)

| 指标 | 场景 | 阈值 |
|------|------|------|
| Cohen's Kappa | 2 个标注者，分类任务 | ≥ 0.6 合格，≥ 0.8 优秀 |
| Fleiss' Kappa | 多个标注者 | 同上 |
| IOU Agreement | 标注框重叠度对比 | ≥ 0.5 合格 |

Kappa < 0.4 → 标注规范需要重新修订。
