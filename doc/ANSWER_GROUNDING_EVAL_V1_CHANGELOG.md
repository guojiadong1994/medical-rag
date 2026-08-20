# Answer Grounding & Generation Evaluation V1 Changelog

## Added

- `src/medical_rag/evaluation/generation_models.py`
  - claim-level grounding models
  - expected-fact coverage models
  - end-to-end report models
- `src/medical_rag/evaluation/generation.py`
  - EvidenceGroundingJudge
  - semantic metrics
  - strict overall-pass calculation
  - Markdown report renderer
- `scripts/judge_rag_answer.py`
  - semantically audits one saved RAG generation
- `scripts/evaluate_generation_e2e.py`
  - runs the current 14-case suite end to end
  - persists checkpoint after every case
- `tests/unit/test_generation_grounding_v1.py`
- `doc/ANSWER_GROUNDING_EVAL_V1.md`

## Reused without changing the task definition

- `doc/evaluation/hypertension_2024_retrieval_eval_v2.json`
  - Query remains unchanged
  - `expected_facts` become the generation correctness target
  - Evidence rules remain the retrieval relevance target

## Important semantic change

Generation V1's `grounding_passed` remains a **structural grounding** signal for backward compatibility.

This stage adds a separate semantic signal:

```text
citation exists
!=
claim is supported by citation
```

Do not merge these concepts in experiment reports.
