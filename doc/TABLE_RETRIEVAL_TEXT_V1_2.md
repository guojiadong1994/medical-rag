# Table Retrieval Text V1.2

## Why this change exists

The PDF parser can preserve an exact numeric fact in `TableBlock.raw_text` even when
virtual-cell reconstruction damages the structured row representation.  The real
hypertension guideline exposed this exact failure mode:

- structured row: `2级高血压 ... 00~10`
- raw layout text: `2级血压(中度) ... 100~109`
- structured row: `3级高血压 ... ≥11`
- raw layout text: `3级高血压 ... ≥110`

Previously the chunker embedded only `search_text`, so the correct values existed in the
parsed object but were invisible to retrieval.

## Method: quality-aware numeric fallback

`TableRetrievalTextBuilder` keeps the structured representation as the primary text.
It then extracts numeric ranges / thresholds from both structured text and raw layout
text.  If a numeric fact exists in raw text but is missing from structured text, only
the raw line containing that missing fact is appended under `数值保真补充`.

This gives us three useful properties:

1. **relationships first**: structured rows remain the primary representation;
2. **exact-value safety**: medical thresholds lost by cell splitting are recovered;
3. **low duplication**: the full raw table is not blindly appended when it adds no new
   numeric evidence, reducing semantic dilution in embeddings.

## Diagnostics

Table chunks now expose metadata:

- `table_retrieval_strategy`
- `table_raw_fallback_used`
- `table_missing_numeric_tokens`
- `table_extraction_strategy`
- `table_quality_flags`

`chunk_report.json` also reports how many table chunks required raw fallback.

## Rerun scope

This version changes chunk construction only. If the current `cleaned_document.json`
already contains `raw_text`, PDF parsing does **not** need to be rerun.

Run:

```bash
python scripts/chunk_document.py data/processed/hypertension_2024/cleaned_document.json
python scripts/embed_chunks.py data/processed/hypertension_2024/chunks.json
python scripts/evaluate_retrieval_methods.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_dense_eval_seed.json \
  --top-k 10
python scripts/diagnose_retrieval_recall.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_dense_eval_seed.json \
  --top-k 10 --candidate-k 30 --deep-k 0 \
  --tag table_retrieval_v1_2
```
