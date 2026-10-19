"""Ingestion flow 02: provide local Legal-BERT embeddings and tokenization."""

from __future__ import annotations

import os
from collections.abc import Sequence

# The prototype does not send local model usage telemetry.
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

class LegalBertEmbedder:
    """Create normalized local embeddings with mean-pooled Legal-BERT."""

    def __init__(
        self,
        model_name: str,
        *,
        local_files_only: bool,
    ) -> None:
        # Import lazily so health checks and mocked tests do not load PyTorch.
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._model = SentenceTransformer(
            model_name,
            local_files_only=local_files_only,
        )

    @property
    def dimension(self) -> int:
        """Return the vector dimension produced by the model."""

        dimension = self._model.get_sentence_embedding_dimension()
        if dimension is None:
            raise RuntimeError("The embedding model does not report a vector dimension.")
        return dimension

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed document or query text without an external model call."""

        if not texts:
            return []
        vectors = self._model.encode(
            list(texts),
            batch_size=16,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]

    def count_tokens(self, text: str) -> int:
        """Count encoder tokens, including the model's special tokens."""

        return len(self._model.tokenizer.encode(text, add_special_tokens=True))

    def offsets_for_chunking(self, text: str) -> list[tuple[int, int]]:
        """Return token character offsets so chunks preserve exact source text."""

        encoded = self._model.tokenizer(
            text,
            add_special_tokens=False,
            return_offsets_mapping=True,
            truncation=False,
        )
        raw_offsets = encoded.get("offset_mapping")
        if raw_offsets is None:
            raise RuntimeError("The embedding tokenizer does not provide text offsets.")
        return [
            (int(start), int(end))
            for start, end in raw_offsets
            if int(end) > int(start)
        ]
