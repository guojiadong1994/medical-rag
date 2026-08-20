from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, Field

from medical_rag.core.config import Settings
from medical_rag.embedding.io import load_chunks, load_manifest, validate_chunks_against_manifest
from medical_rag.embedding.sentence_transformer_embedder import SentenceTransformerEmbedder
from medical_rag.generation.client import OpenAICompatibleChatClient, OpenAICompatibleConfig
from medical_rag.generation.service import GroundedAnswerGenerator, is_abstention_answer
from medical_rag.rag.context import ContextBuilderConfig, RAGContextBuilder
from medical_rag.reranking.hf_sequence_classifier import HFSequenceClassificationReranker
from medical_rag.reranking.hybrid_reranker import HybridRerankerIndex
from medical_rag.retrieval.bm25 import LocalBM25Index
from medical_rag.retrieval.hybrid import ReciprocalRankFusionIndex
from medical_rag.retrieval.local_dense import LocalDenseIndex
from medical_rag.retrieval.milvus_dense import MilvusDenseIndex


class RAGPipelineConfigurationError(RuntimeError):
    pass


class RAGRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    patient_id: str | None = None


class RAGSource(BaseModel):
    citation_id: str
    source_file: str
    page_start: int
    page_end: int
    section: str | None = None
    table_title: str | None = None
    content_type: str
    chunk_id: str
    retrieval_rank: int
    reranker_score: float
    used_in_answer: bool
    text: str


class RAGTiming(BaseModel):
    retrieval_seconds: float
    context_seconds: float
    generation_seconds: float
    total_seconds: float


class RAGDiagnostics(BaseModel):
    dense_backend: str
    embedding_model: str
    reranker_model: str
    generation_model: str
    candidate_k: int
    rerank_k: int
    context_top_k: int
    selected_source_count: int
    used_context_chars: int
    grounding_status: str
    grounding_passed: bool
    cited_ids: list[str] = Field(default_factory=list)
    unknown_citation_ids: list[str] = Field(default_factory=list)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    timing: RAGTiming


class RAGResponse(BaseModel):
    query: str
    answer: str
    abstained: bool
    patient_id: str | None = None
    patient_context_used: bool = False
    sources: list[RAGSource] = Field(default_factory=list)
    diagnostics: RAGDiagnostics


class MedicalRAGPipeline:
    """Product V1 end-to-end medical RAG pipeline.

    The expensive embedding and reranking models are created once and reused.
    A lock serializes inference because the local model/Milvus stack is intended
    as a single-process demo runtime rather than a high-concurrency server.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        retriever: HybridRerankerIndex,
        context_builder: RAGContextBuilder,
        generator: GroundedAnswerGenerator,
        embedding_model_name: str,
        reranker_model_name: str,
    ) -> None:
        self.settings = settings
        self.retriever = retriever
        self.context_builder = context_builder
        self.generator = generator
        self.embedding_model_name = embedding_model_name
        self.reranker_model_name = reranker_model_name
        self._inference_lock = threading.Lock()

    @classmethod
    def from_settings(cls, settings: Settings) -> "MedicalRAGPipeline":
        errors = settings.rag_readiness_errors()
        if errors:
            raise RAGPipelineConfigurationError("; ".join(errors))

        chunks = load_chunks(settings.chunks_path)
        manifest = load_manifest(settings.manifest_path)
        validate_chunks_against_manifest(chunks, manifest)

        # Load the embedding model before Milvus, but do not perform a query
        # forward pass yet. This preserves the macOS MPS + Milvus lifecycle order
        # already verified in Milvus V1.1.
        embedder = SentenceTransformerEmbedder(
            model_name=settings.rag_embedding_model,
            device=settings.rag_embedding_device,
            batch_size=settings.rag_embedding_batch_size,
            normalize_embeddings=manifest.normalized,
            show_progress_bar=False,
        )

        if settings.rag_dense_backend == "milvus":
            dense_index = MilvusDenseIndex(
                uri=settings.rag_milvus_uri,
                collection_name=settings.rag_milvus_collection,
                manifest=manifest,
                token=settings.rag_milvus_token,
            )
            if not dense_index.client.has_collection(
                collection_name=settings.rag_milvus_collection
            ):
                raise RAGPipelineConfigurationError(
                    "Milvus collection does not exist: "
                    f"{settings.rag_milvus_collection!r}. Run scripts/ingest_milvus.py first."
                )
            # Critical lifecycle step: load collection before the first MPS query
            # embedding forward pass.
            dense_index.ensure_loaded()
        else:
            dense_index = LocalDenseIndex.load(
                chunks_path=settings.chunks_path,
                embeddings_path=settings.embeddings_path,
                manifest_path=settings.manifest_path,
            )

        bm25_index = LocalBM25Index(chunks=chunks)
        hybrid_index = ReciprocalRankFusionIndex(
            dense_index=dense_index,
            bm25_index=bm25_index,
            embedder=embedder,
            candidate_k=settings.rag_candidate_k,
            rrf_k=settings.rag_rrf_k,
        )

        reranker = HFSequenceClassificationReranker(
            model_name=settings.rag_reranker_model,
            device=settings.rag_reranker_device,
            batch_size=settings.rag_reranker_batch_size,
            max_length=settings.rag_reranker_max_length,
        )
        retriever = HybridRerankerIndex(
            hybrid_index=hybrid_index,
            reranker=reranker,
            rerank_k=settings.rag_rerank_k,
        )

        context_builder = RAGContextBuilder(
            ContextBuilderConfig(
                top_k=settings.rag_context_top_k,
                max_context_chars=settings.rag_max_context_chars,
            )
        )

        llm_client = OpenAICompatibleChatClient(
            OpenAICompatibleConfig(
                base_url=settings.medical_rag_llm_base_url,
                model=settings.medical_rag_llm_model,
                api_key=settings.medical_rag_llm_api_key,
                temperature=settings.medical_rag_llm_temperature,
                max_output_tokens=settings.medical_rag_llm_max_output_tokens,
                timeout_seconds=settings.medical_rag_llm_timeout_seconds,
            )
        )
        generator = GroundedAnswerGenerator(llm_client)

        return cls(
            settings=settings,
            retriever=retriever,
            context_builder=context_builder,
            generator=generator,
            embedding_model_name=embedder.model_name,
            reranker_model_name=reranker.model_name,
        )

    def ask(self, request: RAGRequest | str) -> RAGResponse:
        if isinstance(request, str):
            request = RAGRequest(query=request)
        query = request.query.strip()
        if not query:
            raise ValueError("query must not be empty")

        with self._inference_lock:
            started = perf_counter()

            retrieval_started = perf_counter()
            retrieval = self.retriever.search(
                query,
                top_k=self.settings.rag_context_top_k,
            )
            retrieval_seconds = perf_counter() - retrieval_started

            context_started = perf_counter()
            context = self.context_builder.build(retrieval)
            context_seconds = perf_counter() - context_started

            generation_started = perf_counter()
            generation = self.generator.generate(context)
            generation_seconds = perf_counter() - generation_started

            total_seconds = perf_counter() - started

        cited = set(generation.citation_validation.cited_ids)
        sources = [
            RAGSource(
                citation_id=source.citation.citation_id,
                source_file=source.citation.source_file,
                page_start=source.citation.page_start,
                page_end=source.citation.page_end,
                section=source.citation.section,
                table_title=source.citation.table_title,
                content_type=source.citation.content_type,
                chunk_id=source.citation.chunk_id,
                retrieval_rank=source.citation.retrieval_rank,
                reranker_score=source.citation.reranker_score,
                used_in_answer=source.citation.citation_id in cited,
                text=source.text,
            )
            for source in context.sources
        ]

        usage = generation.usage
        return RAGResponse(
            query=query,
            answer=generation.answer,
            abstained=is_abstention_answer(generation.answer),
            patient_id=request.patient_id,
            # Patient Timeline fusion belongs to the later patient-specific phase;
            # Product V1 does not pretend patient data was used when it was not.
            patient_context_used=False,
            sources=sources,
            diagnostics=RAGDiagnostics(
                dense_backend=self.settings.rag_dense_backend,
                embedding_model=self.embedding_model_name,
                reranker_model=self.reranker_model_name,
                generation_model=generation.model,
                candidate_k=self.settings.rag_candidate_k,
                rerank_k=self.settings.rag_rerank_k,
                context_top_k=self.settings.rag_context_top_k,
                selected_source_count=context.selected_source_count,
                used_context_chars=context.used_context_chars,
                grounding_status=generation.grounding_check.status,
                grounding_passed=generation.grounding_check.passed,
                cited_ids=list(generation.citation_validation.cited_ids),
                unknown_citation_ids=list(generation.citation_validation.unknown_ids),
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                timing=RAGTiming(
                    retrieval_seconds=round(retrieval_seconds, 4),
                    context_seconds=round(context_seconds, 4),
                    generation_seconds=round(generation_seconds, 4),
                    total_seconds=round(total_seconds, 4),
                ),
            ),
        )

    async def run(self, request: RAGRequest) -> RAGResponse:
        return await asyncio.to_thread(self.ask, request)


def verify_runtime_paths(settings: Settings) -> dict[str, bool]:
    return {
        "chunks": Path(settings.rag_chunks_path).exists(),
        "manifest": Path(settings.rag_manifest_path).exists(),
        "embeddings": Path(settings.rag_embeddings_path).exists(),
        "milvus_file": (
            Path(settings.rag_milvus_uri).exists()
            if "://" not in settings.rag_milvus_uri
            else True
        ),
    }
