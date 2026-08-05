# COCO 数据集标注规范

## 数据集概述

**COCO（Common Objects in Context）** 是由微软研究院发布的大规模视觉数据集，旨在推动目标检测、实例分割、关键点检测和图像字幕等领域的研究。

**关键数据：**
- 发布时间：2014 年（2017 年更新）
- 类别数量：80 个常见物体类别
- 图片数量：超过 33 万张（训练集 118K + 验证集 5K + 测试集 41K + 无标注 123K）
- 标注实例数：超过 250 万个
- 每张图片平均包含 7.7 个实例对象

## 标注任务类型

### 1. 目标检测（Object Detection）

每个目标物体使用一个矩形边界框标注，格式为 `[x, y, width, height]`。

**标注规则要点：**
- **完整标注原则**：标注物体的完整可见区域（包括被遮挡部分，如果可合理推断）
- **极小目标**：面积 < 32×32 像素的目标归类为 `small`
- **人群处理**：密集人群区域使用 `iscrowd=1` 标记，标注为整体区域（非独立个体）
- **遮挡处理**：被遮挡 > 50% 的目标如果仍可被识别，仍需标注

### 2. 实例分割（Instance Segmentation）

为每个目标物体提供像素级的精确轮廓标注。

**标注规则要点：**
- 多边形顶点数量 ≥ 4 个
- 顶点按顺时针方向排列
- 轮廓线紧贴物体边缘，像素级精度
- 被遮挡的轮廓部分按合理推断补充
- 物体的内部孔洞（如甜甜圈的孔）需额外标注为独立多边形

### 3. 关键点检测（Keypoint Detection）

人体关键点检测包含 17 个关键点。

**关键点列表：**
0. 鼻子  1. 左眼  2. 右眼  3. 左耳  4. 右耳
5. 左肩  6. 右肩  7. 左肘  8. 右肘  9. 左腕  10. 右腕
11. 左髋  12. 右髋  13. 左膝  14. 右膝  15. 左踝  16. 右踝

每个关键点标注为 (x, y, v) 三元组，其中 v 为可见性标记（0=不可见，1=可见，2=被遮挡）。

## 标注 JSON 格式详解

```json
{
  "images": [
    {
      "id": 1,
      "file_name": "000000000001.jpg",
      "width": 640,
      "height": 480
    }
  ],
  "annotations": [
    {
      "id": 1,
      "image_id": 1,
      "category_id": 3,
      "bbox": [120.5, 80.2, 200.0, 300.0],
      "segmentation": [[150.5, 90.2, 160.3, 85.5, ...]],
      "area": 50000.0,
      "iscrowd": 0
    }
  ],
  "categories": [
    {
      "id": 3,
      "name": "car",
      "supercategory": "vehicle"
    }
  ]
}
```

**字段说明：**

| 字段 | 含义 |
|------|------|
| images.id | 图片唯一编号 |
| annotations.bbox | [x, y, width, height] — 左上角 x, 左上角 y, 宽度, 高度 |
| annotations.area | 目标区域面积（分割标注用多边形面积，检测标注用 bbox 面积） |
| annotations.iscrowd | 0 = 独立目标，1 = 密集群体 |
| categories.supercategory | 父类别，如 vehicle、animal、person |

## 评估指标

COCO 使用 mAP（mean Average Precision）作为主要评估指标，其特点是：

- **多 IOU 阈值评估**：在 IOU 0.5 到 0.95 之间以 0.05 为步长取 10 个阈值，计算平均 mAP
- **多尺度评估**：small（< 32²）、medium（32² - 96²）、large（> 96²）三类目标的 mAP 分别报告
- **AP50（IOU=0.5）** 是最常用的简化指标

## 教学意义

在标注教学中，COCO 格式是最常用的标准答案格式。教学平台使用 COCO JSON 存储标准答案，使用相同的 IOU 和 mAP 计算逻辑自动评估学员的标注质量。

## 参考

- COCO 官方网站: https://cocodataset.org/
- COCO 标注格式: https://cocodataset.org/#format-data
- COCO API: https://github.com/cocodataset/cocoapi
- Lin, T. Y. et al. (2014). Microsoft COCO: Common Objects in Context. ECCV 2014.
