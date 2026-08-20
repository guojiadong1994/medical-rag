from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from medical_rag.evaluation import EvidenceGroundingJudge, RetrievalEvalSuite
from medical_rag.generation import OpenAICompatibleChatClient, OpenAICompatibleConfig, RAGGenerationResult


def _resolve(cli_value: str | None, *env_names: str) -> str | None:
    if cli_value and cli_value.strip():
        return cli_value.strip()
    for name in env_names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Semantically judge one saved RAG answer against cited evidence and expected facts"
    )
    parser.add_argument("generation_json", type=Path)
    parser.add_argument("--eval-file", type=Path, default=Path("doc/evaluation/hypertension_2024_retrieval_eval_v2.json"))
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--judge-base-url", default=None)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--judge-api-key-env", default="MEDICAL_RAG_JUDGE_API_KEY")
    parser.add_argument("--judge-max-output-tokens", type=int, default=2048)
    parser.add_argument("--judge-timeout", type=float, default=90.0)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    generation = RAGGenerationResult.model_validate_json(args.generation_json.read_text(encoding="utf-8"))
    suite = RetrievalEvalSuite.model_validate_json(args.eval_file.read_text(encoding="utf-8"))
    case = next((item for item in suite.cases if item.id == args.case_id), None)
    if case is None:
        raise SystemExit(f"Unknown case id: {args.case_id}")
    if case.query != generation.query:
        raise SystemExit(
            f"Case/query mismatch: eval query={case.query!r}, generation query={generation.query!r}"
        )

    base_url = _resolve(args.judge_base_url, "MEDICAL_RAG_JUDGE_BASE_URL", "MEDICAL_RAG_LLM_BASE_URL")
    model = _resolve(args.judge_model, "MEDICAL_RAG_JUDGE_MODEL", "MEDICAL_RAG_LLM_MODEL")
    api_key = _resolve(None, args.judge_api_key_env, "MEDICAL_RAG_LLM_API_KEY")
    if not base_url or not model:
        raise SystemExit("Missing judge base URL/model. Judge settings fall back to MEDICAL_RAG_LLM_* if unset.")

    client = OpenAICompatibleChatClient(
        OpenAICompatibleConfig(
            base_url=base_url,
            model=model,
            api_key=api_key,
            temperature=0.0,
            max_output_tokens=args.judge_max_output_tokens,
            timeout_seconds=args.judge_timeout,
        )
    )
    result = EvidenceGroundingJudge(client).judge(generation, case.expected_facts)

    output_dir = args.output_dir or args.generation_json.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "rag_grounding_judgment_v1.json"
    md_path = output_dir / "rag_grounding_judgment_v1.md"
    json_path.write_text(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# RAG Grounding Judgment V1",
        "",
        f"- case_id: {case.id}",
        f"- query: {case.query}",
        f"- judge_model: {result.judge_model}",
        f"- answer_verdict: {result.judgment.answer_verdict}",
        f"- faithfulness_score: {result.metrics.faithfulness_score}",
        f"- expected_fact_coverage: {result.metrics.expected_fact_coverage}",
        f"- fully_grounded: {result.metrics.fully_grounded}",
        f"- answer_correct: {result.metrics.answer_correct}",
        "",
        "## Claim audit",
        "",
    ]
    for claim in result.judgment.claims:
        lines.append(f"- [{claim.verdict}] {claim.claim} | {claim.citation_ids} | {claim.reason}")
    lines.extend(["", "## Expected facts", ""])
    for fact in result.judgment.expected_fact_checks:
        lines.append(f"- [{'OK' if fact.covered else 'MISS'}] {fact.expected_fact} | {fact.reason}")
    lines.extend(["", "## Overall reason", "", result.judgment.overall_reason, ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({
        "case_id": case.id,
        "judge_model": result.judge_model,
        "answer_verdict": result.judgment.answer_verdict,
        "factual_claim_count": result.metrics.factual_claim_count,
        "supported_claim_count": result.metrics.supported_claim_count,
        "unsupported_claim_count": result.metrics.unsupported_claim_count,
        "uncited_claim_count": result.metrics.uncited_claim_count,
        "unclear_claim_count": result.metrics.unclear_claim_count,
        "faithfulness_score": result.metrics.faithfulness_score,
        "expected_fact_coverage": result.metrics.expected_fact_coverage,
        "fully_grounded": result.metrics.fully_grounded,
        "answer_correct": result.metrics.answer_correct,
    }, ensure_ascii=False, indent=2))
    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print("- rag_grounding_judgment_v1.json")
    print("- rag_grounding_judgment_v1.md")


if __name__ == "__main__":
    main()
