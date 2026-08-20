from __future__ import annotations

import argparse
import json
from pathlib import Path

from medical_rag.evaluation import (
    GenerationChallengeSuite,
    GenerationPolicyJudgment,
    GenerationSafetyCaseResult,
    PolicyGroundingEvaluationResult,
    build_generation_safety_report,
    compute_policy_metrics,
    generation_safety_report_markdown,
    policy_case_overall_passed,
    policy_citation_passed,
)
from medical_rag.generation import LLMUsage, RAGGenerationResult


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Offline-rescore an existing Generation Safety V3 report with V3.1 rules. "
            "No retrieval, generation LLM, or judge LLM call is performed."
        )
    )
    parser.add_argument(
        "--source-report",
        type=Path,
        default=Path(
            "data/processed/hypertension_2024/evaluation/generation_safety_eval_v3.json"
        ),
    )
    parser.add_argument(
        "--challenge-eval-file",
        type=Path,
        default=Path("doc/evaluation/hypertension_2024_generation_challenge_v3_1.json"),
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    source = json.loads(args.source_report.read_text(encoding="utf-8"))
    suite = GenerationChallengeSuite.model_validate_json(
        args.challenge_eval_file.read_text(encoding="utf-8")
    )
    case_map = {case.id: case for case in suite.cases}

    results: list[GenerationSafetyCaseResult] = []
    unknown_ids: list[str] = []

    for raw_item in source.get("results", []):
        case_id = raw_item.get("id")
        case = case_map.get(case_id)
        if case is None:
            unknown_ids.append(str(case_id))
            continue

        if raw_item.get("error"):
            results.append(
                GenerationSafetyCaseResult(
                    id=case.id,
                    query=case.query,
                    category=case.category,
                    expected_response_type=case.expected_response_type,
                    expected_facts=case.expected_facts,
                    required_behaviors=case.required_behaviors,
                    forbidden_behaviors=case.forbidden_behaviors,
                    elapsed_seconds=raw_item.get("elapsed_seconds"),
                    error=raw_item.get("error"),
                )
            )
            continue

        generation = RAGGenerationResult.model_validate(raw_item["generation"])
        raw_policy = raw_item["policy_grounding"]
        judgment = GenerationPolicyJudgment.model_validate(raw_policy["judgment"])
        metrics = compute_policy_metrics(judgment, case)
        policy = PolicyGroundingEvaluationResult(
            judgment=judgment,
            metrics=metrics,
            judge_provider=raw_policy.get("judge_provider", "unknown"),
            judge_model=raw_policy.get("judge_model", source.get("judge_model", "unknown")),
            judge_raw_answer=raw_policy.get("judge_raw_answer", ""),
            judge_usage=LLMUsage.model_validate(raw_policy.get("judge_usage", {})),
        )

        policy_citation_ok = policy_citation_passed(generation, policy)
        results.append(
            GenerationSafetyCaseResult(
                id=case.id,
                query=case.query,
                category=case.category,
                expected_response_type=case.expected_response_type,
                expected_facts=case.expected_facts,
                required_behaviors=case.required_behaviors,
                forbidden_behaviors=case.forbidden_behaviors,
                generation=generation,
                policy_grounding=policy,
                structural_unknown_citation_free=not generation.citation_validation.unknown_ids,
                policy_citation_passed=policy_citation_ok,
                overall_passed=policy_case_overall_passed(case, generation, policy),
                elapsed_seconds=raw_item.get("elapsed_seconds"),
            )
        )

    if unknown_ids:
        raise SystemExit(
            "Source report contains case IDs not present in the V3.1 challenge suite: "
            + ", ".join(unknown_ids)
        )
    if not results:
        raise SystemExit("Source report contains no rescorable challenge results")

    report = build_generation_safety_report(
        suite_name=suite.name,
        suite_version=suite.version,
        expected_query_count=len(results),
        generation_model=source.get("generation_model", "unknown"),
        judge_model=source.get("judge_model", "unknown"),
        context_top_k=int(source.get("context_top_k", 5)),
        max_context_chars=int(source.get("max_context_chars", 6000)),
        candidate_k=int(source.get("candidate_k", 50)),
        rerank_k=int(source.get("rerank_k", 20)),
        rrf_k=int(source.get("rrf_k", 60)),
        results=results,
        evaluation_mode="offline_rescore",
        source_report=str(args.source_report),
    )

    output_dir = args.output_dir or args.source_report.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "generation_safety_eval_v3_1_rescored.json"
    md_path = output_dir / "generation_safety_eval_v3_1_rescored.md"
    json_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(generation_safety_report_markdown(report), encoding="utf-8")

    summary = {
        "suite_name": report.suite_name,
        "suite_version": report.suite_version,
        "evaluation_mode": report.evaluation_mode,
        "llm_calls_performed": 0,
        "query_count": report.query_count,
        "completed_count": report.completed_count,
        "error_count": report.error_count,
        "overall_pass_rate": report.overall_pass_rate,
        "policy_citation_pass_rate": report.policy_citation_pass_rate,
        "unanswerable_abstention_accuracy": report.unanswerable_abstention_accuracy,
        "unanswerable_false_answer_rate": report.unanswerable_false_answer_rate,
        "ambiguous_handling_rate": report.ambiguous_handling_rate,
        "apparent_conflict_resolution_rate": report.apparent_conflict_resolution_rate,
        "patient_specific_safety_rate": report.patient_specific_safety_rate,
        "unsafe_advice_rate": report.unsafe_advice_rate,
        "mean_faithfulness_score": report.mean_faithfulness_score,
        "mean_expected_fact_coverage": report.mean_expected_fact_coverage,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nNo LLM call was made. Artifacts written to: {output_dir.resolve()}")
    print("- generation_safety_eval_v3_1_rescored.json")
    print("- generation_safety_eval_v3_1_rescored.md")


if __name__ == "__main__":
    main()
