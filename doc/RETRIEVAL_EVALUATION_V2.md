# Retrieval Evaluation V2：Evidence-level Multi-positive Labels

## 1. 为什么需要 V2

V1 的评测规则虽然不是硬编码单个 `chunk_id`，但很多题仍通过“固定页码 + 固定章节 + 固定关键词”来定义唯一或极窄的 positive evidence。随着 Table Parsing、Hybrid Retrieval 和 Reranker 变强，系统开始把**其他同样正确、甚至更直接的证据**排到前面，而 V1 会把这些证据判为 `relevant=false`。

典型现象：

- “诊室血压诊断阈值”：表6可以直接支持 ≥140/90，但 V1 只承认要点4/4.5.1正文。
- “家庭血压诊断阈值”：表7就是专门的诊断标准表，但 V1 没有把表7作为 positive。
- “夜间动态血压阈值”：6.4.1 直接定义夜间高血压 ≥120/70，但 V1 只承认第10~11页的总结段。
- “白天动态血压阈值”：表21中的“单纯白天高血压”也明确给出 ≥135/85，但 V1 未标正。

如果继续用这种标签优化模型，会出现“模型实际上排得更好，但评测指标反而下降”的假象。

## 2. V2 的核心原则

V2 改为 **Evidence-level Multi-positive Evaluation**：

> 只要一个 Chunk 能够独立、明确支持问题需要的事实，就应该被视为 relevant。

不再要求所有正确答案必须来自某个唯一段落。

### 2.1 多正例

每道题可以定义多个 `evidence_rules`：

```json
{
  "id": "htn_home_threshold",
  "query": "家庭血压诊断高血压的标准是多少？",
  "evidence_rules": [
    {"rule_id": "home_summary_definition", "...": "正文定义"},
    {"rule_id": "home_table7_diagnostic_standard", "...": "表7定义"}
  ]
}
```

命中任何一条规则都算 relevant。

### 2.2 不绑定 Chunk ID

Chunking 版本改变后 `txt_00053` 可能变成 `txt_00054`。因此 V2 仍然优先描述“证据事实”，而不是绑定不稳定的 chunk_id。

规则可以使用：

- `page_ranges`
- `section_contains_any`
- `table_title_contains_any`
- `required_keywords`
- `any_keywords`
- `excluded_keywords`
- `content_types`
- `proximity_groups`

### 2.3 Proximity Rule

仅仅让两个关键词同时出现在一个 800 字 Chunk 中可能太宽松。例如白天阈值与 135/85 可能分别出现在不同语境。

V2 增加：

```json
{
  "proximity_groups": [
    {"keywords": ["白天", "135/85"], "max_chars": 120}
  ]
}
```

要求这些关键词在归一化文本中距离足够近，降低“同 Chunk 不同事实”导致的假阳性。

## 3. V2 评测集

文件：

```text
doc/evaluation/hypertension_2024_retrieval_eval_v2.json
```

当前仍然是 14 道种子题，但已经扩展为 27 条 evidence rule。

V1 文件继续保留：

```text
doc/evaluation/hypertension_2024_dense_eval_seed.json
```

这样可以做 V1/V2 A/B，而不是覆盖历史基线。

## 4. Label Audit

新增：

```bash
python scripts/audit_eval_labels.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_retrieval_eval_v2.json
```

它不加载 Embedding，也不加载 Reranker，只扫描当前 Chunk Corpus，检查：

- 每道题有多少个可接受 evidence chunk；
- 每条 rule 实际匹配多少 Chunk；
- 是否有题 `zero_match`；
- 每条规则的代表性 evidence 示例。

输出：

```text
data/processed/hypertension_2024/evaluation/
├── eval_label_audit_v2.json
└── eval_label_audit_v2.md
```

第一条硬验收标准：

```text
zero_match_case_count = 0
```

第二条不是“匹配越多越好”。如果某条规则突然匹配几十个 Chunk，反而需要人工核查是否过宽。

## 5. 重新评测 Reranker

V2 不需要重新 Parse / Chunk / Embedding。

直接运行：

```bash
python scripts/evaluate_reranker.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_retrieval_eval_v2.json \
  --top-k 10 \
  --candidate-k 50 \
  --rerank-k 20 \
  --tag bge_reranker_base_eval_v2
```

报告现在会额外写出：

- `suite_version`
- 每个 relevant hit 的 `matched_rule_ids`
- Per-query 第一条 positive evidence 是通过哪条规则命中的

这样可以解释“为什么这个 Chunk 被判为正确”，避免评测继续成为黑盒。

## 6. 如何理解 V1 和 V2 的指标差异

如果 V2 的 Recall@1 / MRR 明显高于 V1，不应该解释成“模型突然变强”。模型没有变化，变化的是**标签完整性**。

正确结论应该是：

> V1 存在 incomplete relevance judgments，导致一部分实际正确 evidence 被当成 false negative；V2 对多源等价证据进行补标后，指标更接近真实 retrieval quality。

## 7. 面试知识点

### 不完整相关性标注（Incomplete Relevance Judgments）

信息检索评测中，一个 Query 往往有多个相关文档。如果只标了其中一部分，系统返回未标注但正确的文档时，会被误判为错误。这会低估 Recall、MRR，也可能误导后续优化。

### False Negative

此处不是模型预测里的医疗 false negative，而是**评测标签层面的假阴性**：Chunk 实际正确，但 ground truth 没标成 positive。

### 为什么固定评测集还需要迭代

固定评测集不是“永远不能修改标签”，而是：

1. Query 集合尽量固定，便于 A/B；
2. 发现标签错误时必须修正；
3. 标签版本化（V1 / V2）；
4. 记录修改原因；
5. 不把标签变化误报成模型提升。

这比为了维持旧基线而保留明显错误标签更重要。
