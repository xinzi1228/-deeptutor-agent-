# 标注专业内容来源审计报告（候选）

> 状态：等待人工终审。本报告和清单由程序生成，未修改 60 篇正式资料、题库、评分规则或历史成绩。

## 审计结论

- 共发现 34 处 `GB/T 41867-2022` 高风险误引。
- 官方页面确认该标准名称为《信息技术 人工智能 术语》，不能作为数据标注流程、质量阈值或人员要求的依据。
- `GB/T 42755-2023` 可作为机器学习数据标注流程框架的候选来源，但具体章节、页码和阈值仍需取得合法全文后人工核对。
- 生成式人工智能标注安全场景可候选关联 `GB/T 45674-2025`，不得泛化到全部标注任务。
- 岗位能力和人员培训优先关联《人工智能训练师国家职业技能标准（2021年版）》。

## 候选修订分类

- `align_occupational_competency`：5 处
- `replace_citation_example`：6 处
- `rewrite_standard_overview`：3 处
- `verify_annotation_procedure_claim`：18 处
- `verify_security_scope`：2 处

## 人工终审步骤

1. 取得具有合法使用权的标准全文和教材原文件。
2. 逐条核对章节、页码、定义、阈值和适用范围，不执行全局替换。
3. 无法获得权威依据的教学内容标记为“项目经验”或“示例阈值”。
4. 审核通过后通过内容治理 API 发布新版本，并保留旧答题和初次成绩。
5. 随机抽取不少于 20 道题，复核答案、解析、来源和界面引用是否一致。

## 官方身份来源

- GB/T 41867-2022：https://std.samr.gov.cn/gb/search/gbDetailed?id=EB58F4DA9092B2A2E05397BE0A0A7D33
- GB/T 42755-2023：https://std.samr.gov.cn/gb/search/gbDetailed?id=FC816D04FEB462EBE05397BE0A0AD5FA
- GB/T 45674-2025：https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=407584DD0FA2BA19E62E85D3469290B0
- 人工智能训练师国家职业技能标准（2021年版）：https://www.mohrss.gov.cn/xxgk2020/fdzdgknr/rcrs_4225/jnrc/202112/W020211227626977039770.pdf
