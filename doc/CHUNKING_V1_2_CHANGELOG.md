# Chunking V1.2 Changelog

- 收紧普通整数 Section 识别，降低正文误判为标题的概率。
- 修复 `4.5.1 标题 + 正文` 被整体写进 section 的问题。
- 拒绝百分位、血压阈值、数值范围等正文型伪标题。
- 删除 `表/图/注` 等极短 Narrative 噪声。
- 同 Section 的短正文块在安全条件下合并。
- Chunk 报告区分 Narrative 与 Table 的长度上限统计。
- 新增 `section_audit.json`。
- Dense Retrieval 评测新增 `--tag`，避免覆盖实验结果。
- 评测 Hit 保存文本预览与表格标题。
- 新增逐题 Retrieval Error Analysis 与 baseline 对比脚本。
