# CVAT 标注工具使用指南

**CVAT（Computer Vision Annotation Tool）** 是由 OpenCV 团队开发的专业级开源标注工具，特别适合视频标注和大型团队协作项目。

## CVAT vs Label Studio 对比

| 特性 | CVAT | Label Studio |
|------|------|-------------|
| 开发团队 | OpenCV（Intel） | Heartex |
| 视频标注 | 插值标注、帧间跟踪 | 不支持插值 |
| AI 辅助 | 内置自动标注、服务器端推理 | 需安装 ML Backend |
| 3D 点云标注 | 原生支持 | 有限支持 |
| 团队管理 | 任务分配、角色权限、评审工作流 | 基础团队功能 |
| 学习曲线 | 较陡 | 平缓 |
| 适合场景 | 专业视频标注、大型团队 | 入门教学、通用标注 |

## 安装

**Docker 安装（推荐）：**

```bash
git clone https://github.com/openvinotoolkit/cvat
cd cvat
docker compose up -d
```

首次启动会自动拉取镜像并初始化数据库。访问 `http://localhost:8080`，默认账号为 `admin`，密码在 `docker-compose logs cvat_server` 中查看。

**Windows 本地安装：** CVAT 在 Windows 上需要通过 WSL2（Windows Subsystem for Linux）运行 Docker，建议 Windows 用户使用 Label Studio 入门，CVAT 部署在 Linux 服务器上。

## 核心工作流

### 1. 创建任务

登录后点击 **"Tasks" → "Create new task"**：
- **Name**：任务名称
- **Labels**：定义标签（支持层级标签和属性）
- **Data**：上传图片、视频或压缩包

标签示例（层级结构）：
```
vehicle
  ├── car
  │   ├── sedan
  │   └── SUV
  ├── bus
  └── truck
```

### 2. 主要标注工具

进入标注界面后，左侧工具栏提供以下标注工具：

| 工具 | 快捷键 | 说明 |
|------|--------|------|
| 矩形框 | N | 绘制水平矩形框，可旋转 |
| 多边形 | P | 逐点绘制，双击闭合 |
| 折线 | L | 逐点绘制，用于车道线等 |
| 关键点 | K | 点标注，如人脸关键点 |
| 椭圆 | O | 椭圆标注 |
| 长方体 | Shift+C | 3D 长方体（点云标注） |
| AI 工具 | — | AI 自动检测/跟踪 |

### 3. 视频标注核心功能：插值标注

CVAT 最强大的功能是**插值标注（Interpolation）**：

1. 在第 1 帧绘制目标框并设置关键帧
2. 跳到第 N 帧，调整框的位置和大小
3. CVAT 自动计算中间帧的标注（线性插值）

操作方式：
- **F** 键：跳到下一帧
- **D** 键：跳到上一帧
- 按住 **Shift** 拖动框：快速浏览并调整多帧
- 点击轨迹上的星号（★）设置关键帧

### 4. AI 自动标注

CVAT 内置 AI 工具（需配置 Nuclio 服务器端推理）：

- **Detector**：自动检测图片中的目标
- **Tracker**：视频目标跟踪
- **Interactor**：点击目标后 AI 自动计算贴合框
- **ReID**：跨帧目标重识别

### 5. 评审工作流

CVAT 支持完整的标注评审流程：

```
标注员标注 → 质检员评审（接受/拒绝/批注） → 标注员修正 → 质检员复审 → 通过
```

评审员可以对标注框：
- **Accept**（接受）：标注合格
- **Reject**（拒绝）：标注不合格，需修正
- **Comment**（批注）：提供修改建议

## 数据导出

导出路径：Task → Actions → **"Export task dataset"**，支持格式：

| 格式 | 说明 |
|------|------|
| CVAT for images/video | 原生格式，完整数据 |
| COCO 1.0 | 目标检测标准格式 |
| YOLO 1.1 | YOLO 训练格式 |
| Pascal VOC | 经典检测格式 |
| MOT（多目标跟踪） | 视频跟踪格式 |
| TFRecord | TensorFlow 训练格式 |

## 常见问题

**Q: CVAT 支持中文吗？**  
A: 界面语言为英文，但标签名称支持中文，任务描述支持中文。

**Q: 多人同时标注同一个视频怎么办？**  
A: CVAT 支持将同一个视频拆分为多个 Job，每个标注员负责不同帧范围。

**Q: 标注数据存储在哪里？**  
A: Docker 部署时数据存储在本地的 `cvat_data` 和 `cvat_db` 卷中。建议配置外部存储（S3、NFS）用于生产环境。

**参考：** https://opencv.github.io/cvat/docs/
