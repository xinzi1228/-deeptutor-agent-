# Label Studio 入门指南

**Label Studio** 是开源的数据标注平台，支持图像、文本、音频、视频等多种数据类型标注。

## 安装

```bash
pip install label-studio
label-studio start --port 8080
```

安装完成后浏览器访问 `http://localhost:8080`，注册账号即可开始使用。Label Studio 支持 Windows、macOS 和 Linux 三大平台，建议使用 Python 3.8 及以上版本。

## 核心概念

| 概念 | 说明 |
|------|------|
| **项目（Project）** | 一个标注任务集合，包含标注配置、数据集和标注人员 |
| **标注配置（Labeling Config）** | 使用 XML 定义标注界面，决定标注员能看到什么控件（矩形框、多边形、分类选项等） |
| **任务（Task）** | 单个待标注的数据项，可以是一张图片、一段文本、一段音频 |
| **标注（Annotation）** | 标注人员完成的一个标注结果，包含所有框、标签、分类信息 |
| **预测（Prediction）** | 预标注结果，由模型自动生成，标注员审核修正后可转为正式标注 |

## 快速上手五步走

### 第一步：创建项目
登录后点击右上角 **"Create"** 按钮，输入项目名称（如"车辆检测标注项目"），点击创建。

### 第二步：导入数据
进入项目后点击 **"Import"**，支持以下方式导入数据：
- 直接上传图片文件（支持 jpg、png、bmp、tiff 等格式）
- 导入 JSON 文件（适用于已有标注结果的任务）
- 导入 CSV 文件（批量导入图片 URL）
- 通过云存储同步（AWS S3、GCS、Azure Blob）

### 第三步：配置标注界面
点击 **"Settings" → "Labeling Interface"**，选择模板或编写自定义 XML 配置。Label Studio 提供多种预设模板：
- 图像分类（Image Classification）
- 目标检测（Object Detection with Bounding Boxes）
- 语义分割（Semantic Segmentation）
- 文本分类（Text Classification）
- 命名实体识别（NER）

### 第四步：开始标注
配置完成后进入标注界面，左侧显示图片，右侧显示标注控件。使用鼠标绘制矩形框、选择标签，完成后点击 **"Submit"** 提交当前标注，自动跳转到下一张。

### 第五步：导出结果
标注完成后点击 **"Export"**，选择导出格式：
- **JSON**：最完整的标注结果，包含元数据和标注详情
- **CSV**：适合统计分析
- **COCO JSON**：目标检测常用格式
- **YOLO TXT**：YOLO 训练格式
- **Pascal VOC XML**：经典检测格式

## 矩形框标注配置示例

```xml
<View>
  <Image name="image" value="$image"/>
  <RectangleLabels name="label" toName="image">
    <Label value="car" background="#FF0000"/>
    <Label value="person" background="#00FF00"/>
    <Label value="bicycle" background="#0000FF"/>
  </RectangleLabels>
</View>
```

该配置创建一个目标检测标注界面，包含三个类别：汽车（红色框）、行人（绿色框）、自行车（蓝色框）。

## 常见问题

**Q: Label Studio 需要 GPU 吗？**  
A: 纯标注不需要 GPU。如果使用 ML Backend 做预标注，则需要 GPU 运行模型。

**Q: 多人可以同时标注一个项目吗？**  
A: 可以。在项目设置中添加成员，多人可同时标注不同任务。Label Studio 会自动分配任务避免重复。

**Q: 如何迁移数据到另一台服务器？**  
A: 导出项目（含任务和标注），在新服务器导入即可。大规模迁移建议直接迁移 SQLite/PostgreSQL 数据库。

**参考：** https://labelstud.io/guide/
