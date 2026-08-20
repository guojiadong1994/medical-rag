# Context Builder V1

## 目标

检索与重排序解决“找哪些证据、按什么顺序排列”，但这些结果不能直接无结构地塞给 LLM。Context Builder V1 增加一个确定性的上下文装配层，把 Reranker Top-K 转换成可控、可追溯、可引用的 LLM Context。

当前稳定上游保持不变：

`BGE-M3 Dense + BM25 -> RRF(candidate_k=50) -> BGE Reranker(rerank_k=20)`

本阶段只新增：

`Reranker Top5 -> Context Builder -> [S1]...[S5] -> Grounded Prompt Preview`

## 为什么需要 Context Builder

直接拼接 Top-K 会产生四类工程问题：

1. 来源身份丢失：LLM 回答后无法知道事实来自哪个 Chunk、哪一页。
2. 上下文无限增长：Top-K、Chunk 变大后 Prompt 成本和噪声同步增加。
3. 重复证据浪费 Token：相同内容可能由重叠 Chunk 或重复段落产生。
4. Citation 无法验证：如果没有固定来源 ID，LLM 很容易生成不存在的引用。

## V1 设计

### 1. Rank-preserving selection

严格保持 Reranker 排名，不在 Context Builder 内再次“偷偷排序”。这保证一次只改变一个变量。

### 2. Stable per-answer citation ID

每次回答从高到低分配：`[S1]`、`[S2]`、`[S3]`……

每个 Citation 保留：

- chunk_id
- document_id
- source_file
- page_start / page_end
- section / section_path
- content_type
- table_title
- retrieval_rank
- reranker_score
- pre_rerank_rank

### 3. Context budget

默认 `max_context_chars=6000`。V1 以字符数做可解释、易调试的预算；后续接具体 LLM 时再升级成 tokenizer-aware token budget。

如果最后一个来源超预算，但仍可保留足够正文，则截断并显式写入 `…[上下文预算截断]`；不会静默截断。

### 4. Conservative deduplication

V1 只删除“去除空白后完全相同”的重复文本，不做语义去重，避免误删两个看起来相似但医学条件不同的证据。

### 5. Grounded prompt

Prompt 明确要求：

- 只根据当前 Evidence 回答；
- 关键医学事实句末必须引用 `[Sx]`；
- 不允许编造不存在的 Source ID；
- 冲突证据分别说明；
- 证据不足明确回答不足；
- 不把一般指南知识变成针对具体患者的个体化诊断/处方。

### 6. Citation syntax validation

`validate_answer_citations()` 可以检查生成答案是否引用了不存在的 `[S9]` 等 Source ID。这只是 Citation Safety 的第一层；后续还会做 claim-to-evidence grounding 检查。

## 为什么本阶段仍使用 Local Dense 构建完整链路

Milvus V1.1 已经通过 Local Dense vs Milvus Top10 `overlap_ratio=1.0`、`same_rank_ratio=1.0` 的一致性验收。Context Builder V1 的实验变量是“上下文装配”，不是“检索后端”。因此脚本继续使用已经稳定的 Local Dense + BM25 + RRF + Reranker，避免把 Milvus backend integration 与 Context Builder 同时改动。

下一阶段会在真正的 RAG Pipeline/API 组装时把 Dense backend 设为可配置（Local/Milvus）。

## 验收

运行：

```bash
python scripts/build_rag_context.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的收缩压和舒张压范围是多少？" \
  --context-top-k 5 \
  --max-context-chars 6000
```

检查：

- `selected_source_count` 是否 3~5；
- `citation_ids` 是否从 `S1` 连续编号；
- `rag_context_v1.md` 中页面、章节、表格来源是否正确；
- `rag_prompt_preview_v1.md` 中是否只出现这些真实 Source ID；
- 关键表6证据是否进入 Context。

## 下一阶段

LLM Generation V1：引入 LLM Adapter、真正生成 answer，并进行 Citation syntax validation、无证据拒答与初步 grounded-answer evaluation。
