from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from medical_rag.evaluation import GenerationChallengeSuite, RetrievalEvalSuite


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Generation Safety Evaluation V3 suite before LLM calls")
    parser.add_argument(
        "--positive-eval-file",
        type=Path,
        default=Path("doc/evaluation/hypertension_2024_retrieval_eval_v2.json"),
    )
    parser.add_argument(
        "--challenge-eval-file",
        type=Path,
        default=Path("doc/evaluation/hypertension_2024_generation_challenge_v3.json"),
    )
    args = parser.parse_args()

    positive = RetrievalEvalSuite.model_validate_json(args.positive_eval_file.read_text(encoding="utf-8"))
    challenge = GenerationChallengeSuite.model_validate_json(args.challenge_eval_file.read_text(encoding="utf-8"))

    positive_ids = [case.id for case in positive.cases]
    challenge_ids = [case.id for case in challenge.cases]
    overlap = sorted(set(positive_ids) & set(challenge_ids))

    category_counts = Counter(case.category for case in challenge.cases)
    response_counts = Counter(case.expected_response_type for case in challenge.cases)

    missing_required = [case.id for case in challenge.cases if not case.required_behaviors]
    missing_forbidden = [case.id for case in challenge.cases if not case.forbidden_behaviors]

    report = {
        "positive_suite": positive.name,
        "positive_case_count": len(positive.cases),
        "challenge_suite": challenge.name,
        "challenge_case_count": len(challenge.cases),
        "combined_case_count": len(positive.cases) + len(challenge.cases),
        "category_counts": dict(category_counts),
        "expected_response_type_counts": dict(response_counts),
        "duplicate_ids_across_suites": overlap,
        "challenge_cases_missing_required_behaviors": missing_required,
        "challenge_cases_missing_forbidden_behaviors": missing_forbidden,
        "audit_passed": not overlap and not missing_required and not missing_forbidden,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if not report["audit_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
