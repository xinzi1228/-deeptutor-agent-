# Pascal VOC 标注格式

## Pascal VOC 概述

**Pascal VOC（Visual Object Classes）** 是由牛津大学、利兹大学等多个研究机构联合发起的视觉识别挑战赛，从 2005 年持续到 2012 年。虽然挑战赛已结束，但其定义的 XML 标注格式至今仍被广泛使用，是计算机视觉领域的经典标注格式之一。

**数据集规模（VOC 2012）：**
- 20 个目标类别（人、动物、交通工具、室内物品四大类）
- 约 1.1 万张训练/验证图片
- 约 2.7 万个标注目标
- 标注任务：分类、检测、分割

## XML 标注格式详解

每张图片对应一个同名的 XML 文件，结构如下：

```xml
<annotation>
    <folder>VOC2012/JPEGImages</folder>
    <filename>2007_000001.jpg</filename>
    <source>
        <database>The VOC2007 Database</database>
        <annotation>PASCAL VOC2007</annotation>
    </source>
    <size>
        <width>640</width>
        <height>480</height>
        <depth>3</depth>
    </size>
    <segmented>0</segmented>
    <object>
        <name>car</name>
        <pose>Frontal</pose>
        <truncated>1</truncated>
        <difficult>0</difficult>
        <occluded>0</occluded>
        <bndbox>
            <xmin>100</xmin>
            <ymin>200</ymin>
            <xmax>350</xmax>
            <ymax>450</ymax>
        </bndbox>
        <part>
            <name>wheel</name>
            <bndbox>
                <xmin>120</xmin>
                <ymin>400</ymin>
                <xmax>160</xmax>
                <ymax>440</ymax>
            </bndbox>
        </part>
    </object>
    <object>
        <name>person</name>
        ...
    </object>
</annotation>
```

## 关键字段说明

| XML 字段 | 数据类型 | 含义 |
|----------|---------|------|
| `folder` | string | 图片所在文件夹名称 |
| `filename` | string | 图片文件名 |
| `size/width` | int | 图片宽度（像素） |
| `size/height` | int | 图片高度（像素） |
| `size/depth` | int | 图片通道数（RGB 为 3） |
| `object/name` | string | 目标类别名称（如 car, person, dog） |
| `bndbox/xmin` | int | 边界框左上角 x 坐标 |
| `bndbox/ymin` | int | 边界框左上角 y 坐标 |
| `bndbox/xmax` | int | 边界框右下角 x 坐标 |
| `bndbox/ymax` | int | 边界框右下角 y 坐标 |
| `truncated` | 0 或 1 | 目标是否被图片边界截断 |
| `difficult` | 0 或 1 | 是否为难例（难例可不参与评测） |
| `occluded` | 0 或 1 | 目标是否被遮挡 |
| `pose` | string | 目标姿态（Frontal, Rear, Left, Right 等） |

## VOC 坐标系统

- **坐标系原点**：图片左上角 (0, 0)
- **bbox 格式**：(xmin, ymin) 为矩形左上角坐标，(xmax, ymax) 为矩形右下角坐标
- **注意**：这与 COCO 格式的 `[x, y, width, height]` 不同——VOC 使用两个角点，COCO 使用左上角 + 宽高

## 格式转换：VOC ↔ COCO

### VOC → COCO

```python
# 给定 VOC 标注
xmin, ymin, xmax, ymax = ...

# 转换为 COCO 格式
coco_x = xmin
coco_y = ymin
coco_width = xmax - xmin
coco_height = ymax - ymin
coco_bbox = [coco_x, coco_y, coco_width, coco_height]
```

### COCO → VOC

```python
# 给定 COCO 标注
x, y, width, height = ...

# 转换为 VOC 格式
voc_xmin = x
voc_ymin = y
voc_xmax = x + width
voc_ymax = y + height
```

## VOC 20 类别列表

**Person 类：** person
**Animal 类：** bird, cat, cow, dog, horse, sheep
**Vehicle 类：** aeroplane, bicycle, boat, bus, car, motorbike, train
**Indoor 类：** bottle, chair, dining table, potted plant, sofa, tv/monitor

## 教学要点

1. **坐标系理解**：强调 VOC 用的是"左上角 + 右下角"两个角点定义框，而非"左上角 + 宽高"
2. **属性字段**：讲解 `truncated`、`difficult`、`occluded` 等属性字段的作用和填写规范
3. **XML 文件命名**：标注 XML 文件必须与对应图片文件同名（除扩展名外）
4. **实操练习**：让学员手动标注并生成 VOC XML，用验证工具检查 XML 格式是否正确

## 参考

- Pascal VOC 官方网站: http://host.robots.ox.ac.uk/pascal/VOC/
- VOC 2012 标注规范: http://host.robots.ox.ac.uk/pascal/VOC/voc2012/guidelines.html
- 《数据标注工程》第 4 章 标注格式与工具
