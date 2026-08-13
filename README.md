# 标注星图 — 数据标注教学智能体

基于 [DeepTutor](https://github.com/HKUDS/DeepTutor) 二次开发，定制为**数据标注教学平台**「标注星图」。

## 功能

- **标注教练 Persona** — AI 以标注导师身份对话，出题、检查、指导（界面全中文）
- **多专家教学体系** — 诊断/出题/分析/监督/反思 6 角色协作，自动 readiness 判定
- **标注题库** — 12 个真实任务（车辆/马匹检测、动物分类、标准合规、改错题），5 种题型
- **标注检查工具** — 自动计算 IOU/F1/精确率/召回率，逐框反馈
- **Canvas 标注工作台** — 鼠标画框标注，内置即时检查
- **Label Studio 集成** — 嵌入 LS 作为专业标注界面（可选增强，不装不影响核心教学）
- **记忆追踪** — Coach 记录每次练习成绩，推荐渐进式学习路径
- **多学习档案** — 同一系统账号可为不同学生切换独立 PIN 档案，对话、记忆、练习和报告互不混用
- **能力中心** — 用新手能看懂的方式完成模型体检、资料快速导入、Skill/MCP 状态检查和初始化
- **可信生成式可视化** — 对话可输出带来源与单位的图表、流程图和用户模型生成的插画
- **教学轨迹/流程可视化** — 进度面板、回合链追溯、能力雷达
- **规范引用溯源** — 引用标注标准（GB/T 41867-2022 等）时给出可点击出处
- **定时学习提醒 + 免登录分享 + 生成式练习卡片**

## 快速开始

> 环境要求：**Python 3.11–3.13**、**Node.js 20+**（Windows 需同时有 `pip` 与 `npm` 在 PATH）。

### 1. 安装依赖

```bash
# Python 后端（建议在 conda 虚拟环境中执行）
cd DeepTutor
pip install -e .

# 前端 (需要 Node.js 20)
cd web
npm install
```

> Windows 提示：若 `pip install` 编译失败，先装 [Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)，或用 conda 环境（`conda create -n deeptutor python=3.11`）。

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
# 方式1: 使用启动脚本（一键起后端+前端，Windows 双击即可）
start_all.bat

# 方式2: 分别启动
# 终端1 - 后端
python -m uvicorn deeptutor.api.main:app --host 0.0.0.0 --port 8001

# 终端2 - 前端
# 注意: 必须设 DEEPTUTOR_API_BASE_URL 指向 127.0.0.1（localhost 会解析到 ::1，
#       而后端只绑 IPv4，不设会连不上）
set DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001
cd web
npx next dev --port 3782

# 终端3 - Label Studio (可选，专业标注界面增强；不装不影响核心教学)
start_label_studio.bat
#   - 管理员首次登录后创建服务 Token，学生不使用这个账号
#   - 标注星图后端通过受控网关建项目、导数据并建立隐藏会话：
#     set LABEL_STUDIO_URL=http://localhost:8080
#     set LABEL_STUDIO_API_TOKEN=<你的 LS token>
#     set LABEL_STUDIO_BRIDGE_SECRET=<独立随机长字符串>
```

### 4. 验证安装

```bash
# 后端能跑（命令行直接对话测试）
deeptutor run chat "你好"
# 或后端起来后访问 http://127.0.0.1:8001/docs 看接口文档
```

### 4. 使用

打开 `http://localhost:3782`：
- **Chat 页** → 选 `annotation-coach` Persona → 说"我要练习标注"
- **Annotation 页** → 左侧菜单 → 选任务 → 鼠标画框 → 点"检查标注"
  - 顶部可切教学图片/文本/音频/视频与专业模式；专业模式由同源网关直达本人任务，不需要再次登录 Label Studio
- **能力中心** → 左侧“能力中心” → 查看缺失配置、导入第一份资料、下载脱敏体检报告

## Label Studio（专业标注界面）

> 可选增强。不装不影响核心教学（Chat 出题 + Canvas 画框检查）。演示"专业标注界面"卖点时使用。

```bash
# 1. 安装
pip install label-studio

# 2. 一键启动（自动初始化数据库 + 账号）
start_label_studio.bat
# 或手动：label-studio start --init --data-dir data/label-studio --username admin@localhost --password admin123 --port 8080

# 3. 管理员访问 http://localhost:8080 完成首次配置；学生不要从这里登录
```

- **学生入口**：Annotation 页 →「专业模式」；页面嵌入的是标注星图同源网关，不是把 8080 管理台直接暴露给学生
- **Coach 自动建项目/导数据**：后端 `label_studio_tool` 通过 REST API 工作，需设置：
  - `LABEL_STUDIO_URL=http://localhost:8080`
  - `LABEL_STUDIO_API_TOKEN=<LS 的 API token>`（LS 账号页 → Account & Settings → Access Token）
  - `LABEL_STUDIO_BRIDGE_SECRET=<独立随机长字符串>`（用于派生每个学习档案的隐藏会话凭证）
- **数据位置**：`data/label-studio/`（运行时数据，已在 .gitignore）

## 项目结构

```
DeepTutor/
├── deeptutor/
│   ├── tools/
│   │   ├── annotation_check.py      # 标注检查引擎 (IOU/F1计算)
│   │   ├── task_bank_tool.py        # 题库工具 (12任务 5题型)
│   │   ├── render_ui_tool.py        # 生成式UI (练习卡片)
│   │   └── label_studio_tool.py     # Label Studio 集成
│   ├── services/persona/presets/
│   │   └── annotation-coach/        # 标注教练人设 (多专家+规范引用+定时提醒)
│   └── skills/builtin/
│       └── annotation-guide/        # 标注知识技能 (规范库→引用溯源)
├── web/
│   ├── app/(workspace)/
│   │   ├── annotation/page.tsx      # 标注工作台页面
│   │   ├── progress/                # 进度可视化 (概览/记录/成就/图谱)
│   │   ├── standards/               # 规范库页
│   │   ├── tasks/                   # 定时任务管理页
│   │   └── home/.../page.tsx        # Chat页 (含自动检测标注结果)
│   ├── public/
│   │   ├── annotation_tool.html     # Canvas标注工具
│   │   └── images/                  # 标注图片 (课程数据集)
│   └── components/sidebar/
│       └── SidebarShell.tsx         # 侧边栏 (Annotation入口)
└── data/
    └── user/workspace/
        ├── task_bank.json           # 题库数据 (已进git)
        ├── competency_tree.json     # 能力树 (已进git)
        └── question_bank.json       # 备用题库
```

## 数据集来源

标注图片和 ground truth 来自课程《数据标注课件+案例+素材》，包含：
- 车辆检测（街景/特写/停车场）
- 马匹检测
- 动物分类（鸡/兔/鼠）

## 致谢

基于 [DeepTutor](https://github.com/HKUDS/DeepTutor) (HKUDS Lab) 和 [Label Studio](https://github.com/HumanSignal/label-studio) (HumanSignal)。
教学体系借鉴：[edumcp](https://github.com/aieducations/edumcp) · [lumen](https://github.com/ahmedEid1/lumen) · [feynman-tutor](https://github.com/koukekoukej-glitch/feynman-tutor) · [agency-agents](https://github.com/msitarzewski/agency-agents) · [ag-ui](https://github.com/ag-ui-protocol/ag-ui) 等（完整清单见 `docs/august-changes-record.md`）。
