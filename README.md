# DeepTutor Agent — 数据标注教学智能体

基于 [DeepTutor](https://github.com/HKUDS/DeepTutor) 二次开发，定制为**数据标注教学平台**。

## 功能

- **标注教练 Persona** — AI 以标注导师身份对话，出题、检查、指导
- **标注题库** — 从课程数据集解析的 5 个真实标注任务（车辆检测、马匹检测、动物分类）
- **标注检查工具** — 自动计算 IOU/F1/精确率/召回率，逐框反馈
- **Canvas 标注工作台** — 鼠标画框标注，内置即时检查
- **Label Studio 集成** — 嵌入 LS 作为专业标注界面
- **记忆追踪** — Coach 记录每次练习成绩，推荐渐进式学习路径

## 快速开始

### 1. 安装依赖

```bash
# Python 后端
cd DeepTutor
pip install -e .

# 前端 (需要 Node.js 20)
cd web
npm install
```

### 2. 配置 LLM

创建 `data/user/settings/model_catalog.json`，配置 DeepSeek（或其他 OpenAI 兼容 API）：

```json
{
  "services": {
    "llm": {
      "active_profile_id": "deepseek",
      "profiles": [{
        "id": "deepseek",
        "binding": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "你的API Key",
        "models": [{"id": "default", "model": "deepseek-chat"}]
      }]
    }
  }
}
```

### 3. 启动

```bash
# 方式1: 使用启动脚本
start_all.bat

# 方式2: 分别启动
# 终端1 - 后端
python -m uvicorn deeptutor.api.main:app --host 0.0.0.0 --port 8001

# 终端2 - 前端 (先设 Node 20 PATH)
npx next dev --port 3782

# 终端3 - Label Studio (可选)
label-studio start --port 8080
```

### 4. 使用

打开 `http://localhost:3782`：
- **Chat 页** → 选 `annotation-coach` Persona → 说"我要练习标注"
- **Annotation 页** → 左侧菜单 → 选任务 → 鼠标画框 → 点"检查标注"

## 项目结构

```
DeepTutor/
├── deeptutor/
│   ├── tools/
│   │   ├── annotation_check.py      # 标注检查引擎 (IOU/F1计算)
│   │   ├── task_bank_tool.py        # 题库工具 (课程数据)
│   │   └── label_studio_tool.py     # Label Studio 集成
│   ├── services/persona/presets/
│   │   └── annotation-coach/        # 标注教练人设
│   └── skills/builtin/
│       └── annotation-guide/        # 标注知识技能
├── web/
│   ├── app/(workspace)/
│   │   ├── annotation/page.tsx      # 标注工作台页面
│   │   └── home/.../page.tsx        # Chat页 (含自动检测标注结果)
│   ├── public/
│   │   ├── annotation_tool.html     # Canvas标注工具
│   │   └── images/                  # 标注图片 (课程数据集)
│   └── components/sidebar/
│       └── SidebarShell.tsx         # 侧边栏 (Annotation入口)
└── data/
    └── user/workspace/
        ├── task_bank.json           # 题库数据
        └── question_bank.json       # 备用题库
```

## 数据集来源

标注图片和 ground truth 来自课程《数据标注课件+案例+素材》，包含：
- 车辆检测（街景/特写/停车场）
- 马匹检测
- 动物分类（鸡/兔/鼠）

## 致谢

基于 [DeepTutor](https://github.com/HKUDS/DeepTutor) (HKUDS Lab) 和 [Label Studio](https://github.com/HumanSignal/label-studio) (HumanSignal)。
