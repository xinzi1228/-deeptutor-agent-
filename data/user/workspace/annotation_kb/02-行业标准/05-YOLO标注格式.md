# YOLO 标注格式

## YOLO 概述

YOLO（You Only Look Once）是由 Joseph Redmon 等人提出的实时目标检测算法系列，以其极快的推理速度闻名。YOLO 系列使用独特的纯文本标注格式（TXT 文件），简洁高效，已成为工业界最广泛使用的目标检测标注格式之一。

**YOLO 发展历程：**
- YOLOv1（2015）：首次提出统一检测框架
- YOLOv3（2018）：引入多尺度特征融合，使用 Darknet-53 骨干网络
- YOLOv5（2020）：Ultralytics 实现，工业部署最广泛的版本
- YOLOv8（2023）：Ultralytics 最新版本，支持检测、分割、分类、姿态估计

## YOLO 标注格式规范

### 文件结构

```
dataset/
├── data.yaml              # 数据集配置文件
├── images/
│   ├── train/
│   │   ├── 001.jpg
│   │   └── 002.jpg
│   └── val/
│       ├── 003.jpg
│       └── 004.jpg
├── labels/
│   ├── train/
│   │   ├── 001.txt       # 与图片同名，扩展名为 .txt
│   │   └── 002.txt
│   └── val/
│       ├── 003.txt
│       └── 004.txt
└── classes.txt            # 类别名称列表（部分版本使用）
```

### TXT 文件格式

每行代表一个目标框，格式为：

```
class_id x_center y_center width height
```

**所有坐标值均为归一化坐标（除以图片宽高后的值，范围 0 到 1）。**

**示例文件（001.txt）：**
```
0 0.718750 0.497917 0.093750 0.129167
1 0.335938 0.606250 0.084375 0.175000
0 0.250000 0.858333 0.125000 0.283333
```

### 字段详解

| 字段 | 含义 | 取值范围 |
|------|------|---------|
| class_id | 类别编号，从 0 开始（对应 classes.txt 中的行号顺序） | 0 到 (N-1)，N 为类别总数 |
| x_center | 目标框中心点的 x 坐标（归一化） | 0 到 1 |
| y_center | 目标框中心点的 y 坐标（归一化） | 0 到 1 |
| width | 目标框的宽度（归一化） | 0 到 1 |
| height | 目标框的高度（归一化） | 0 到 1 |

### classes.txt 文件

类别名称列表，一行一个类别。顺序决定了 class_id 的数值。

```
person
car
bicycle
motorcycle
bus
truck
traffic_light
stop_sign
```

### data.yaml 配置文件

```yaml
train: ./images/train
val: ./images/val
nc: 8                    # 类别总数
names: ['person', 'car', 'bicycle', 'motorcycle', 'bus', 'truck', 'traffic_light', 'stop_sign']
```

## 格式转换公式

### VOC（xmin, ymin, xmax, ymax）→ YOLO

```
x_center = (xmin + xmax) / 2 / image_width
y_center = (ymin + ymax) / 2 / image_height
width = (xmax - xmin) / image_width
height = (ymax - ymin) / image_height
```

### COCO（x, y, w, h）→ YOLO

```
x_center = (x + w / 2) / image_width
y_center = (y + h / 2) / image_height
width = w / image_width
height = h / image_height
```

### YOLO → VOC

```
xmin = (x_center - width / 2) * image_width
ymin = (y_center - height / 2) * image_height
xmax = (x_center + width / 2) * image_width
ymax = (y_center + height / 2) * image_height
```

## YOLO 格式的优点

1. **极致简洁**：纯文本格式，每张图一个 txt 文件，无需解析复杂结构
2. **空间高效**：归一化坐标占用空间小，无需存储图片尺寸信息
3. **训练即用**：YOLO 训练脚本直接读取，无需格式转换
4. **易于生成和检查**：人工可以直接阅读和修改 txt 文件

## 常见错误与注意事项

| 错误 | 说明 |
|------|------|
| 坐标未归一化 | 直接使用像素坐标（如 320 500）而忘记除以图片宽高 |
| 坐标超出 [0,1] | 归一化计算错误导致坐标 > 1 或 < 0 |
| class_id 超出范围 | class_id 超出 classes.txt 中定义的类别总数 |
| 图片与标注不匹配 | 图片文件名和标注文件名不一致（大小写、空格等） |
| 空文件 | 图片中无目标时，标注 txt 应为空文件而非缺失 |

## 教学要点

1. **归一化概念**：让学员理解归一化坐标与绝对像素坐标的区别，用实际图片举例演示转换过程
2. **手动标注练习**：让学员在工具中标注图片，导出 YOLO 格式，再反向验证（读取 YOLO txt 文件在图片上可视化画出框）
3. **格式转换练习**：给定 VOC/COCO 标注，手动计算转换为 YOLO 格式

## 参考

- Ultralytics YOLO 官方文档: https://docs.ultralytics.com/datasets/detect/
- YOLOv5 Train Custom Data: https://github.com/ultralytics/yolov5/wiki/Train-Custom-Data
- Darknet YOLO 标注格式说明
