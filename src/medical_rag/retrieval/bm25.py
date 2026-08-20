from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass

from medical_rag.chunking.models import DocumentChunk
from medical_rag.embedding.io import load_chunks
from medical_rag.retrieval.models import BM25SearchHit, BM25SearchResponse


_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_LATIN_NUMERIC_RE = re.compile(
    r"(?:[<>≥≤]?\d+(?:\.\d+)?(?:[~\-/]\d+(?:\.\d+)?)?(?:mmhg|mg|g|ml|h|d|%|级|期)?)"
    r"|(?:[a-z]+(?:[-_/][a-z0-9]+)*)",
    re.IGNORECASE,
)


class MedicalBM25Tokenizer:
    """Deterministic tokenizer for mixed Chinese medical text.

    The first BM25 baseline deliberately avoids an external Chinese segmenter. Chinese
    text is represented by overlapping 2-gram/3-gram features, while Latin words,
    abbreviations, numeric thresholds and ranges are preserved as exact tokens. This is
    especially useful for medical values such as ``135/85``, ``100~109`` and ``CKD``.
    """

    name = "medical_cjk_2_3gram_v1"

    _LEVEL_MAP = {
        "一级": "1级",
        "二级": "2级",
        "三级": "3级",
        "四级": "4级",
        "五级": "5级",
        "六级": "6级",
        "七级": "7级",
        "八级": "8级",
        "九级": "9级",
        "十级": "10级",
    }

    def normalize(self, text: str) -> str:
        value = unicodedata.normalize("NFKC", text or "").lower()
        value = value.replace("～", "~").replace("−", "-").replace("—", "-")
        for source, target in self._LEVEL_MAP.items():
            value = value.replace(source, target)
        # Make common units robust to PDF whitespace: ``24 h`` -> ``24h``.
        value = re.sub(r"(?<=\d)\s+(?=(?:mmhg|mg|ml|h|d|%|级|期)\b)", "", value)
        return value

    def tokenize(self, text: str) -> list[str]:
        value = self.normalize(text)
        tokens: list[str] = []

        # Exact alphanumeric / numeric features.
        tokens.extend(match.group(0) for match in _LATIN_NUMERIC_RE.finditer(value))

        # Character n-grams are stable for Chinese and avoid depending on a dictionary.
        for match in _CJK_RE.finditer(value):
            run = match.group(0)
            if len(run) == 1:
                tokens.append(run)
                continue
            for n in (2, 3):
                if len(run) < n:
                    continue
                tokens.extend(run[i : i + n] for i in range(len(run) - n + 1))
        return tokens


@dataclass(slots=True)
class _Posting:
    doc_index: int
    term_frequency: int


class LocalBM25Index:
    """Small in-memory BM25 index used as the sparse retrieval baseline."""

    def __init__(
        self,
        *,
        chunks: list[DocumentChunk],
        tokenizer: MedicalBM25Tokenizer | None = None,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if k1 <= 0:
            raise ValueError("k1 must be positive")
        if not 0 <= b <= 1:
            raise ValueError("b must be between 0 and 1")
        self.chunks = chunks
        self.tokenizer = tokenizer or MedicalBM25Tokenizer()
        self.k1 = float(k1)
        self.b = float(b)

        self.doc_lengths: list[int] = []
        postings: dict[str, list[_Posting]] = defaultdict(list)
        document_frequency: Counter[str] = Counter()

        for doc_index, chunk in enumerate(chunks):
            # Use the same retrieval-facing representation as dense embedding: section
            # context + chunk text. That keeps the BM25/Dense comparison fair.
            tokens = self.tokenizer.tokenize(chunk.embedding_text)
            self.doc_lengths.append(len(tokens))
            counts = Counter(tokens)
            for term, frequency in counts.items():
                postings[term].append(_Posting(doc_index, frequency))
                document_frequency[term] += 1

        self.postings = dict(postings)
        self.document_frequency = document_frequency
        self.avg_doc_length = (
            sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0.0
        )
        total_docs = max(len(chunks), 1)
        self.idf = {
            term: math.log(1.0 + (total_docs - df + 0.5) / (df + 0.5))
            for term, df in document_frequency.items()
        }

    @classmethod
    def load(
        cls,
        chunks_path,
        *,
        tokenizer: MedicalBM25Tokenizer | None = None,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> "LocalBM25Index":
        return cls(
            chunks=load_chunks(chunks_path),
            tokenizer=tokenizer,
            k1=k1,
            b=b,
        )

    def search(self, query: str, *, top_k: int = 5) -> BM25SearchResponse:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if not self.chunks:
            return BM25SearchResponse(
                query=query,
                tokenizer_name=self.tokenizer.name,
                top_k=top_k,
                hits=[],
            )

        query_counts = Counter(self.tokenizer.tokenize(query))
        scores: dict[int, float] = defaultdict(float)
        avgdl = self.avg_doc_length or 1.0

        for term, query_tf in query_counts.items():
            idf = self.idf.get(term)
            if idf is None:
                continue
            for posting in self.postings.get(term, []):
                doc_index = posting.doc_index
                tf = posting.term_frequency
                dl = self.doc_lengths[doc_index]
                denominator = tf + self.k1 * (1.0 - self.b + self.b * dl / avgdl)
                term_score = idf * (tf * (self.k1 + 1.0)) / denominator
                # Repeated query terms are rare, but honoring qtf keeps the formula
                # deterministic and intuitive.
                scores[doc_index] += term_score * query_tf

        ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]
        hits: list[BM25SearchHit] = []
        for rank, (doc_index, score) in enumerate(ordered, start=1):
            chunk = self.chunks[doc_index]
            hits.append(
                BM25SearchHit(
                    rank=rank,
                    score=round(float(score), 6),
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    source_file=chunk.source_file,
                    content_type=chunk.content_type,
                    section=chunk.section,
                    section_path=list(chunk.section_path),
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    text=chunk.text,
                    table_title=chunk.table_title,
                    table_no=chunk.table_no,
                )
            )

        return BM25SearchResponse(
            query=query,
            tokenizer_name=self.tokenizer.name,
            top_k=top_k,
            hits=hits,
        )
