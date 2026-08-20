from __future__ import annotations

import json
from pathlib import Path

from medical_rag.evaluation import (
    EvidenceRule,
    KeywordProximityRule,
    RetrievalEvalCase,
    RetrievalEvalSuite,
    evaluate_retriever,
    matching_rule_ids,
)
from medical_rag.retrieval.models import DenseSearchHit


def _hit(
    *,
    chunk_id: str = "c1",
    text: str,
    section: str | None = None,
    table_title: str | None = None,
    content_type: str = "narrative",
    page: int = 10,
    rank: int = 1,
) -> DenseSearchHit:
    return DenseSearchHit(
        rank=rank,
        score=1.0,
        chunk_id=chunk_id,
        document_id="doc",
        source_file="guide.pdf",
        content_type=content_type,  # type: ignore[arg-type]
        section=section,
        section_path=[] if section is None else [section],
        page_start=page,
        page_end=page,
        text=text,
        table_title=table_title,
    )


def test_multi_positive_rules_accept_narrative_or_table_evidence() -> None:
    rules = [
        EvidenceRule(
            rule_id="narrative",
            section_contains_any=["4.5.1"],
            required_keywords=["家庭血压", "135/85"],
        ),
        EvidenceRule(
            rule_id="table7",
            content_types=["table"],
            table_title_contains_any=["表7"],
            required_keywords=["家庭血压", "135", "85"],
        ),
    ]

    narrative = _hit(
        text="家庭血压≥135/85 mmHg可诊断高血压。",
        section="4.5.1 按血压水平分类和分级",
    )
    table = _hit(
        text="家庭血压 连续5~7d规范化测量 ≥135 和/或 ≥85",
        table_title="表7 基于诊室血压、家庭血压和动态血压的高血压诊断标准",
        content_type="table",
        page=11,
    )

    assert matching_rule_ids(narrative, rules) == ["narrative"]
    assert matching_rule_ids(table, rules) == ["table7"]


def test_proximity_rule_blocks_unrelated_same_chunk_terms() -> None:
    rule = EvidenceRule(
        rule_id="day_threshold",
        required_keywords=["135/85"],
        proximity_groups=[KeywordProximityRule(keywords=["白天", "135/85"], max_chars=30)],
    )

    close = _hit(text="单纯白天高血压定义为白天血压≥135/85 mmHg。")
    far = _hit(text="白天动态血压用于评估。" + "无关内容" * 30 + "135/85 mmHg是另一个指标。")

    assert matching_rule_ids(close, [rule]) == ["day_threshold"]
    assert matching_rule_ids(far, [rule]) == []


def test_excluded_keywords_can_prevent_known_false_positive() -> None:
    rule = EvidenceRule(
        rule_id="diagnosis_not_target",
        required_keywords=["家庭血压", "135/85"],
        excluded_keywords=["治疗目标"],
    )
    hit = _hit(text="家庭血压治疗目标<135/85 mmHg。")
    assert matching_rule_ids(hit, [rule]) == []


def test_evaluation_report_records_matched_rule_ids() -> None:
    suite = RetrievalEvalSuite(
        name="v2-test",
        version="v2",
        cases=[
            RetrievalEvalCase(
                id="home",
                query="家庭血压诊断标准？",
                evidence_rules=[
                    EvidenceRule(
                        rule_id="home_direct",
                        required_keywords=["家庭血压", "135/85"],
                    )
                ],
            )
        ],
    )
    hits = [
        _hit(
            rank=1,
            text="家庭血压≥135/85 mmHg可诊断高血压。",
        )
    ]
    report = evaluate_retriever(
        suite,
        search=lambda _query, _k: hits,
        retriever_name="dense",
        top_k=5,
    )

    assert report.suite_version == "v2"
    assert report.recall_at_1 == 1.0
    assert report.results[0].relevant_hit_count == 1
    assert report.results[0].hits[0].matched_rule_ids == ["home_direct"]


def test_v1_seed_remains_backward_compatible() -> None:
    root = Path(__file__).resolve().parents[2]
    path = root / "doc/evaluation/hypertension_2024_dense_eval_seed.json"
    suite = RetrievalEvalSuite.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert suite.version == "v1"
    assert len(suite.cases) == 14


def test_v2_seed_has_multi_positive_threshold_rules() -> None:
    root = Path(__file__).resolve().parents[2]
    path = root / "doc/evaluation/hypertension_2024_retrieval_eval_v2.json"
    suite = RetrievalEvalSuite.model_validate(json.loads(path.read_text(encoding="utf-8")))
    by_id = {case.id: case for case in suite.cases}

    assert suite.version == "v2"
    assert len(suite.cases) == 14
    assert len(by_id["htn_office_threshold"].evidence_rules) >= 3
    assert len(by_id["htn_home_threshold"].evidence_rules) >= 2
    assert len(by_id["htn_abpm_night_threshold"].evidence_rules) >= 3
    assert by_id["htn_home_threshold"].expected_facts
