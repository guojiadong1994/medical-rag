from __future__ import annotations

from collections.abc import Sequence


DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-base"


def _resolve_torch_device(requested: str | None) -> str:
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "PyTorch is not installed. Run: pip install -e \".[dev,embedding,reranker]\""
        ) from exc

    value = (requested or "auto").lower()
    if value != "auto":
        return requested or value
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class HFSequenceClassificationReranker:
    """Cross-encoder style reranker backed by Hugging Face Transformers.

    The query and each candidate passage are encoded *together*. This is slower than
    dense retrieval, but it lets the model directly reason over fine-grained token
    interactions, which is exactly what we want after a high-recall first stage.

    Scores are raw sequence-classification logits. They are intentionally not exposed
    as probabilities because the model card does not guarantee calibrated probability
    semantics. Only the relative ordering matters for reranking.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_RERANKER_MODEL,
        *,
        device: str | None = "auto",
        batch_size: int = 4,
        max_length: int = 512,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if max_length <= 0:
            raise ValueError("max_length must be positive")

        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Reranker dependencies are not installed. "
                'Run: pip install -e ".[dev,embedding,reranker]"'
            ) from exc

        self._torch = torch
        self._model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        self._device = _resolve_torch_device(device)

        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self._model.eval()
        self._model.to(self._device)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def device(self) -> str:
        return self._device

    def score(self, query: str, documents: Sequence[str]) -> list[float]:
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("query must not be empty")

        clean_documents = [document.strip() for document in documents]
        if any(not document for document in clean_documents):
            raise ValueError("reranker documents must not be empty")
        if not clean_documents:
            return []

        scores: list[float] = []
        for start in range(0, len(clean_documents), self.batch_size):
            batch = clean_documents[start : start + self.batch_size]
            queries = [clean_query] * len(batch)
            encoded = self._tokenizer(
                queries,
                batch,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(self._device) for key, value in encoded.items()}

            with self._torch.inference_mode():
                logits = self._model(**encoded, return_dict=True).logits

            if logits.ndim == 2 and logits.shape[1] == 1:
                batch_scores = logits[:, 0]
            elif logits.ndim == 1:
                batch_scores = logits
            else:
                raise ValueError(
                    "reranker model must output one relevance logit per query-document pair; "
                    f"got logits shape={tuple(logits.shape)}"
                )
            scores.extend(float(value) for value in batch_scores.detach().float().cpu().tolist())

        if len(scores) != len(clean_documents):
            raise RuntimeError("reranker returned an unexpected number of scores")
        return scores
