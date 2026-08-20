# Answer Grounding & End-to-End Generation Evaluation V1

## 1. 这一阶段解决什么问题

LLM Generation V1 已经能验证 `[S1]` 是否真实存在，但这只是**结构合法性**：

- `[S1]` 存在：结构上合法；
- 但答案中的医学事实是否真的被 `[S1]` 支持：此前还无法自动判断。

本阶段新增语义评测层，把“引用编号合法”和“证据真正支持事实”分开。

## 2. 三层质量信号

### 2.1 Structural Citation

确定性程序检查：

- 有没有引用；
- 有没有引用不存在的 `[S9]`；
- 引用 ID 是否属于本次 Context。

### 2.2 Claim-to-Evidence Faithfulness

使用受约束的 Judge LLM：

1. 从答案抽取医学事实 claim；
2. 找出 claim 实际引用的 `[Sx]`；
3. 只查看该证据；
4. 判定 `supported / unsupported / uncited / unclear`。

注意：**citation valid != semantic support**。

### 2.3 Expected-Fact Coverage / Answer Correctness

继续复用 Retrieval Evaluation V2 中人工整理的 `expected_facts`，判断答案是否覆盖问题真正要求的核心事实。

这使检索评测和生成评测共享同一套人工任务定义，而不是临时让 Judge 自己发明“标准答案”。

## 3. 指标

- `structural_citation_pass_rate`：引用结构合格比例；
- `faithfulness_score`：supported claims / factual claims；
- `fully_grounded_rate`：每个事实 claim 都被其引用证据支持的比例；
- `expected_fact_coverage`：回答覆盖 expected facts 的比例；
- `answer_correct_rate`：Judge 判为 correct 且 expected facts 全覆盖；
- `overall_pass_rate`：结构引用通过 + answer correct + fully grounded 全部满足。

`overall_pass_rate` 是故意设置得比较严格的指标。

## 4. Judge 的边界

V1 使用 LLM-as-Judge，因此它不是绝对真值：

- 同模型既生成又评测，会存在 self-judge bias；
- Judge 可能误判复杂医学条件；
- 14 条种子题样本量小。

因此报告必须记录 generation model 和 judge model。正式实验建议：

1. 先用同一模型低成本跑通；
2. 再选择独立 Judge 模型复核；
3. 对失败项和随机样本做人审。

不要把 Judge 分数描述为临床正确率。

## 5. 先单题审计

对已经生成的 `rag_generation_v1.json`：

```bash
python scripts/judge_rag_answer.py \
  data/processed/hypertension_2024/rag/rag_generation_v1.json \
  --case-id grade2_bp
```

Judge 配置默认优先读取：

```text
MEDICAL_RAG_JUDGE_BASE_URL
MEDICAL_RAG_JUDGE_MODEL
MEDICAL_RAG_JUDGE_API_KEY
```

如果没有单独设置 Judge，则 base URL / model / key 会回退到 `MEDICAL_RAG_LLM_*`。

## 6. 再跑 14 道端到端评测

```bash
python scripts/evaluate_generation_e2e.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_retrieval_eval_v2.json \
  --context-top-k 5 \
  --max-context-chars 6000 \
  --candidate-k 50 \
  --rerank-k 20
```

每道题会执行：

```text
Dense + BM25
→ RRF
→ Reranker
→ Context Builder
→ Generation LLM
→ Structural Citation Validation
→ Semantic Judge
→ Per-case metrics
```

默认会持续写 `generation_e2e_checkpoint_v1.json`，所以即使第 11 题网络失败，前 10 题结果仍然保留。

## 7. 为什么暂时不评 Refusal Accuracy

当前 14 道种子题都是指南内可回答问题，没有专门的“知识库中不存在答案”负样本。

所以本阶段**不伪造 refusal accuracy**。后续 Evaluation V3 会增加 answerable / unanswerable / ambiguous / conflict 等安全样本，再正式评价拒答能力。

## 8. 面试怎么说

> 我把 RAG 评测拆成 retrieval 和 generation 两层。Retrieval 用 Recall@K/MRR；Generation 不能只看最终答案，还要区分 citation validity 和 semantic faithfulness。我先用确定性规则检查 `[Sx]` 是否真实存在，再用受约束的 LLM Judge 将回答拆成 claim，逐条判断 cited evidence 是否支持，同时复用人工 expected facts 评估答案覆盖度。这样能识别“引用编号合法但引用内容不支持结论”的隐性幻觉。
