# Python 批量标注处理

标注项目中经常需要对大量标注文件进行批量处理——格式转换、标签验证、坐标修正、质量统计等。Python 凭借丰富的库和简洁的语法，成为批量标注处理的首选语言。

## 环境准备

```bash
pip install Pillow opencv-python lxml tqdm pycocotools
```

常用库说明：
- **Pillow**：读取图片尺寸和格式信息
- **OpenCV**：图像处理、可视化标注框
- **lxml**：解析 VOC XML 标注文件
- **pycocotools**：处理 COCO 格式数据集
- **tqdm**：显示批处理进度条

## 场景一：批量 VOC XML → COCO JSON 转换

这是最常见的格式转换需求，适用于将所有标注统一为 COCO 训练格式：

```python
import os
import json
import glob
from xml.etree import ElementTree as ET
from tqdm import tqdm

def voc_to_coco(voc_dir, output_json_path):
    images = []
    annotations = []
    categories = []
    category_name_to_id = {}
    annotation_id = 1

    xml_files = glob.glob(os.path.join(voc_dir, "*.xml"))
    for image_id, xml_file in enumerate(tqdm(xml_files), start=1):
        tree = ET.parse(xml_file)
        root = tree.getroot()

        filename = root.find("filename").text
        width = int(root.find("size/width").text)
        height = int(root.find("size/height").text)

        images.append({
            "id": image_id,
            "file_name": filename,
            "width": width,
            "height": height
        })

        for obj in root.findall("object"):
            name = obj.find("name").text.strip()
            bbox = obj.find("bndbox")
            xmin = int(bbox.find("xmin").text)
            ymin = int(bbox.find("ymin").text)
            xmax = int(bbox.find("xmax").text)
            ymax = int(bbox.find("ymax").text)

            if name not in category_name_to_id:
                cat_id = len(category_name_to_id) + 1
                category_name_to_id[name] = cat_id
                categories.append({"id": cat_id, "name": name})

            annotations.append({
                "id": annotation_id,
                "image_id": image_id,
                "category_id": category_name_to_id[name],
                "bbox": [xmin, ymin, xmax - xmin, ymax - ymin],
                "area": (xmax - xmin) * (ymax - ymin),
                "iscrowd": 0
            })
            annotation_id += 1

    coco_data = {
        "images": images,
        "annotations": annotations,
        "categories": categories
    }

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(coco_data, f, ensure_ascii=False, indent=2)

    print(f"转换完成：{len(images)} 张图片，{len(annotations)} 个标注框")

# 使用示例
voc_to_coco("./voc_annotations/", "./coco_annotations.json")
```

## 场景二：批量标签验证

检查所有标注文件中的标签是否都在允许的标签列表中，防止非标准标签混入：

```python
def validate_labels(annotations_dir, allowed_labels, format_type="voc"):
    """验证标注文件中的标签是否合法"""
    errors = []
    allowed = set(allowed_labels)

    for ann_file in glob.glob(os.path.join(annotations_dir, "*")):
        if format_type == "voc" and ann_file.endswith(".xml"):
            tree = ET.parse(ann_file)
            for obj in tree.getroot().findall("object"):
                label = obj.find("name").text.strip()
                if label not in allowed:
                    errors.append({
                        "file": os.path.basename(ann_file),
                        "label": label,
                        "reason": f"标签 '{label}' 不在允许的标签列表 {allowed_labels} 中"
                    })

    if errors:
        print(f"发现 {len(errors)} 个标签错误：")
        for e in errors:
            print(f"  - {e['file']}: {e['reason']}")
    else:
        print(f"验证通过：所有标签均合法")
    return errors
```

## 场景三：批量重命名标签

统一不同批次标注中的标签名称，例如将 `automobile` 统一为 `car`：

```python
def batch_rename_labels(annotations_dir, label_mapping):
    """批量重命名标注文件中的标签"""
    renamed_count = 0

    for ann_file in glob.glob(os.path.join(annotations_dir, "*.xml")):
        tree = ET.parse(ann_file)
        modified = False
        for obj in tree.getroot().findall("object"):
            old_name = obj.find("name").text.strip()
            if old_name in label_mapping:
                obj.find("name").text = label_mapping[old_name]
                modified = True
                renamed_count += 1

        if modified:
            tree.write(ann_file, encoding="utf-8", xml_declaration=True)

    print(f"重命名完成：共修改 {renamed_count} 个标签")
```

## 场景四：坐标边界修正

确保标注框坐标在图片范围内，修正越界坐标：

```python
def fix_bbox_bounds(annotations_dir, img_dir):
    """修正超出图片边界的标注框"""
    fixed_count = 0

    for ann_file in glob.glob(os.path.join(annotations_dir, "*.xml")):
        tree = ET.parse(ann_file)
        root = tree.getroot()

        filename = root.find("filename").text
        img_path = os.path.join(img_dir, filename)
        if not os.path.exists(img_path):
            continue

        from PIL import Image
        img_w, img_h = Image.open(img_path).size
        modified = False

        for obj in root.findall("object"):
            bbox = obj.find("bndbox")
            coords = {
                "xmin": max(0, int(bbox.find("xmin").text)),
                "ymin": max(0, int(bbox.find("ymin").text)),
                "xmax": min(img_w, int(bbox.find("xmax").text)),
                "ymax": min(img_h, int(bbox.find("ymax").text))
            }

            for key, val in coords.items():
                old_val = int(bbox.find(key).text)
                if old_val != val:
                    bbox.find(key).text = str(val)
                    modified = True
                    fixed_count += 1

        if modified:
            tree.write(ann_file, encoding="utf-8", xml_declaration=True)

    print(f"边界修正完成：共修正 {fixed_count} 处越界坐标")
```

## 场景五：标注可视化批处理

批量生成标注可视化图片，用于人工快速核查标注质量：

```python
import cv2
import numpy as np

def visualize_annotations(img_dir, ann_dir, output_dir):
    """批量绘制标注框并保存可视化图片"""
    label_colors = {
        "car": (0, 0, 255),      # 红色
        "person": (0, 255, 0),   # 绿色
        "bicycle": (255, 0, 0)   # 蓝色
    }

    for ann_file in tqdm(glob.glob(os.path.join(ann_dir, "*.xml"))):
        tree = ET.parse(ann_file)
        root = tree.getroot()
        filename = root.find("filename").text

        img_path = os.path.join(img_dir, filename)
        if not os.path.exists(img_path):
            continue

        img = cv2.imread(img_path)
        for obj in root.findall("object"):
            label = obj.find("name").text.strip()
            bbox = obj.find("bndbox")
            x1, y1 = int(bbox.find("xmin").text), int(bbox.find("ymin").text)
            x2, y2 = int(bbox.find("xmax").text), int(bbox.find("ymax").text)

            color = label_colors.get(label, (255, 255, 255))
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            cv2.putText(img, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        out_path = os.path.join(output_dir, filename)
        cv2.imwrite(out_path, img)
```

## 批量处理最佳实践

1. **先在小样本上验证**：取 5-10 个标注文件先测试脚本，确认无误后再全量运行
2. **保留原始备份**：批量修改前务必备份原始标注文件
3. **使用进度条监控**：`tqdm` 库让批处理过程可视化，便于判断处理速度
4. **记录日志**：将修改内容输出到日志文件，方便追溯和问题排查
5. **单元测试验证**：为转换函数编写单元测试，确保坐标转换公式正确
