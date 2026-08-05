# Label Studio 任务导入导出

标注项目的起点是数据导入，终点是结果导出。掌握导入导出操作是标注项目管理的核心能力。

## 任务导入

### 支持的导入格式

| 格式 | 适用场景 | 说明 |
|------|---------|------|
| JSON | 通用 | 包含数据路径和可选预标注 |
| CSV | 批量导入 | 每行一个任务，列名为字段名 |
| TSV | 文本数据 | 类似 CSV，制表符分隔 |
| 纯文本 | 简单场景 | 每行一个文本/URL |
| 压缩包 | 批量图片 | 直接上传 zip 文件 |

### JSON 格式导入（推荐）

JSON 是最灵活的导入格式，支持同时导入数据和预标注结果：

```json
[
  {
    "data": {
      "image": "/data/upload/1/001.jpg"
    }
  },
  {
    "data": {
      "image": "/data/upload/1/002.jpg"
    },
    "predictions": [
      {
        "result": [
          {
            "original_width": 1920,
            "original_height": 1080,
            "value": {
              "x": 100,
              "y": 150,
              "width": 300,
              "height": 200,
              "rectanglelabels": ["car"]
            },
            "type": "rectanglelabels"
          }
        ]
      }
    ]
  }
]
```

**关键字段说明：**
- `data`：任务数据，字段名需与 Labeling Config 中的 `value` 属性对应
- `predictions`：预标注结果（可选），模型预测的标注，标注员审核后可转为正式标注
- `annotations`：已有标注结果（可选），直接导入历史标注数据
- `id`：任务 ID（可选），不指定则自动生成

### CSV 格式导入

```csv
image_url,caption
http://example.com/img001.jpg,"街道场景，晴天"
http://example.com/img002.jpg,"街道场景，雨天"
```

CSV 导入会自动将每行转换为一个任务，列名映射为任务数据的字段名。Label Studio 会自动检测图片 URL、文本、音频 URL 等数据类型。

### 云存储导入

Label Studio 支持从云存储直接导入，避免上传大量文件：

- **AWS S3**：`s3://bucket-name/path/to/images/`
- **Google Cloud Storage**：`gs://bucket-name/path/to/images/`
- **Azure Blob Storage**：`https://account.blob.core.windows.net/container/`
- **Redis**（推荐）：适合大规模数据，支持增量导入

配置路径：项目 Settings → Cloud Storage → Add Source Storage。

## 任务导出

### 导出方式

**方式一：Web 界面导出**

进入项目页面，点击 **"Export"** 按钮，选择导出格式，点击 Download。Web 导出适合小规模数据（< 10000 任务）。

**方式二：API 导出**

```bash
# 导出 JSON 格式
curl -X GET "http://localhost:8080/api/projects/{project_id}/export?exportType=JSON" \
  -H "Authorization: Token YOUR_API_TOKEN" \
  -o annotations.json

# 导出 COCO 格式
curl -X GET "http://localhost:8080/api/projects/{project_id}/export?exportType=COCO" \
  -H "Authorization: Token YOUR_API_TOKEN" \
  -o annotations_coco.json
```

API 导出适合自动化流程和 CI/CD 集成。

### 支持的导出格式

| 格式 | 说明 | 适用场景 |
|------|------|---------|
| JSON | 完整标注数据，含元数据 | 通用备份、数据迁移 |
| JSON_MIN | 精简 JSON，仅含标注结果 | 模型训练 |
| CSV | 表格格式 | 数据分析与统计 |
| COCO JSON | COCO 数据集格式 | 目标检测/分割训练 |
| YOLO TXT | YOLO 训练格式 | YOLO 系列模型训练 |
| Pascal VOC XML | VOC 格式 | 经典检测模型训练 |
| Brush to PNG | 笔刷标注转 PNG 掩码 | 语义分割训练 |

### JSON 导出结构解析

```json
[
  {
    "id": 1,
    "data": {
      "image": "/data/upload/1/001.jpg"
    },
    "annotations": [
      {
        "id": 101,
        "completed_by": {"id": 1, "email": "annotator@example.com"},
        "result": [
          {
            "id": "box_001",
            "type": "rectanglelabels",
            "value": {
              "x": 100, "y": 150,
              "width": 300, "height": 200,
              "rectanglelabels": ["car"]
            },
            "original_width": 1920,
            "original_height": 1080
          }
        ],
        "was_cancelled": false,
        "created_at": "2026-07-31T10:00:00Z"
      }
    ]
  }
]
```

**重要字段：**
- `completed_by`：标注人信息，用于计算标注一致性
- `result`：标注结果数组，一个任务可以包含多个标注区域
- `was_cancelled`：标注是否被取消（跳过）
- `created_at`：创建时间，用于标注进度追踪

### 导出注意事项

1. **导出前确认**：检查是否所有任务都已完成标注，未标注的任务不会出现在导出结果中
2. **格式兼容性**：COCO 导出需要标注配置包含目标检测或分割控件；纯分类项目不支持 COCO 导出
3. **大项目导出**：超过 10000 个任务建议使用 API 分批导出，避免浏览器超时
4. **UTF-8 编码**：导出 CSV 时确保使用 UTF-8 编码，避免中文标签乱码

**参考：** https://labelstud.io/guide/export.html
