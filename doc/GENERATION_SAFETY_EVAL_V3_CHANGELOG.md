# Generation Safety Evaluation V3 Changelog

- 新增 `GenerationChallengeSuite` 与 9 条困难/安全样本。
- 新增 `GenerationSafetyJudge`：同时评估 claim grounding、expected facts、required/forbidden behaviors、unsafe advice。
- 新增 answer / abstain / conditional / safe_boundary 四种预期响应类型。
- 新增 False Refusal / False Answer / Abstention Accuracy / Patient Safety 等指标。
- 新增 `scripts/audit_generation_eval_v3.py`。
- 新增 `scripts/evaluate_generation_safety_v3.py`，支持 `--challenge-only`、`--positive-only`、`--category`、`--case-id`。
- 保留 Evaluation V2 14 条正例作为稳定 baseline，不覆盖旧评测文件。
- 新增 checkpoint 与 generation/judge token 分开统计。
- 单元测试由 40 增至 49，全部通过。
