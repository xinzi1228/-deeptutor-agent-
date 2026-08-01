# 工具使用指南

> 适用阶段: Phase2 实践 Step4 (评测分析)

## annotation_check 工具

**何时调用:**
- 用户完成标注并提交结果后
- 需要对 bbox 标注做 IOU/Precision/Recall/F1 评测
- 需要对分类标注做 Accuracy 评测

**参数:**
- `predictions`: JSON 数组 — 用户的标注 `[{"x":..., "y":..., "w":..., "h":..., "label":"..."}]`
- `ground_truth`: JSON 数组 — 标准答案（从 task_bank 获取）
- `task_type`: "bbox"（目标检测）| "classification"（分类）

**返回值:**
- bbox: F1 / Precision / Recall + 逐框匹配详情（正确/标签错/漏标/多余）
- classification: Accuracy

**使用注意:**
- ground_truth 来自 get_annotation_task 的返回，不要手动编造
- 评分后必须调用 write_memory 记录进度
- F1 < 0.7 时，反馈后应推荐学生回 Phase1 理论复习

## get_annotation_task 工具

**何时调用:**
- Phase2 Step1: 学生说"我要练习"时
- Phase0 Step3: 摸底测验需要展示任务素材时

**参数:**
- `task_id`: "task1" ~ "task9"

**可用任务:**
- task1-4: bbox easy/medium
- task5,9: classification
- task6-8: bbox hard（遮挡/密集目标/精度）

## Label Studio 工具

**ls_create_project:** 创建 LS 标注项目（需 LS 运行在 localhost:8080）
**ls_check_annotations:** 导出 LS 项目结果 + 自动评测（需 LABEL_STUDIO_API_TOKEN）
