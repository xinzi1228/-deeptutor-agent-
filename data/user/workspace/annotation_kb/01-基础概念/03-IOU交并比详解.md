# IOU（交并比）详解

## 定义

IOU（Intersection over Union，交并比）是衡量两个边界框重叠程度的指标，是目标检测标注质量评价中最核心的量化指标。其计算公式为交集面积与并集面积的比值。

## 数学公式

```
IOU(A, B) = Area(A ∩ B) / Area(A ∪ B)
```

其中：
- **A ∩ B**：预测框 A 与真值框 B 的重叠区域面积（交集）
- **A ∪ B**：预测框 A 与真值框 B 覆盖的总面积（并集）
- 并集可以展开为：Area(A) + Area(B) - Area(A ∩ B)

## 坐标计算

给定两个矩形框，其坐标分别为：
- 框 A（真值框）：(x1_A, y1_A) 左上角，(x2_A, y2_A) 右下角
- 框 B（预测框）：(x1_B, y1_B) 左上角，(x2_B, y2_B) 右下角

**交集计算步骤：**

1. 计算重叠区域的左上角坐标：
   - inter_x1 = max(x1_A, x1_B)
   - inter_y1 = max(y1_A, y1_B)

2. 计算重叠区域的右下角坐标：
   - inter_x2 = min(x2_A, x2_B)
   - inter_y2 = min(y2_A, y2_B)

3. 计算交集面积：
   - inter_w = max(0, inter_x2 - inter_x1 + 1)
   - inter_h = max(0, inter_y2 - inter_y1 + 1)
   - inter_area = inter_w * inter_h

4. 计算两个框的面积：
   - area_A = (x2_A - x1_A + 1) * (y2_A - y1_A + 1)
   - area_B = (x2_B - x1_B + 1) * (y2_B - y1_B + 1)

5. 计算 IOU：
   - iou = inter_area / (area_A + area_B - inter_area)

## IOU 取值含义

| IOU 值 | 含义 | 判定 |
|--------|------|------|
| IOU = 1.0 | 两个框完全重合 | 完美标注 |
| 0.7 ≤ IOU < 1.0 | 高度重叠 | 标注质量良好 |
| 0.5 ≤ IOU < 0.7 | 中度重叠 | 标注基本合格（常用判定阈值） |
| 0.3 ≤ IOU < 0.5 | 低度重叠 | 标注不合格，需要整改 |
| IOU < 0.3 | 几乎不重叠 | 标注严重偏离，必须重标 |
| IOU = 0 | 完全不重叠 | 两个框没有任何交集 |

## 教学目标

在数据标注教学中，IOU 是考核学员标注质量的首要指标。教学要点包括：

1. **直观理解**：用两个相交的矩形框可视化演示，帮助学员理解交集和并集的概念
2. **边界情况**：讲解边框不完全包含目标（框太小）和边框过于宽松（框太大）对 IOU 的影响
3. **实践练习**：让学员在标注工具中标注同一张图片，系统自动计算 IOU 分数并给出改进建议

## 进阶概念

- **GIOU（Generalized IOU）**：在 IOU 基础上引入最小外接矩形，解决两个不相交框无法比较梯度的问题
- **DIOU（Distance IOU）**：引入中心点距离惩罚项
- **CIOU（Complete IOU）**：同时考虑重叠面积、中心点距离和长宽比

## 参考

- GB/T 41867-2022 附录 A
- Intersection over Union (IoU) for Object Detection (Papers with Code)
- 《数据标注工程》第 6 章 质量评价方法
