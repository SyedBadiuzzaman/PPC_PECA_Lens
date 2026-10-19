"""Runtime core 02: retrieve from one local legal collection."""

from __future__ import annotations

from src.core_04.guardrails_04.guardrail_02_retrieval import usable_chunks
from src.domain_01.domain_01_enums import Law
from src.domain_01.domain_03_models import RetrievedChunk
from src.ingestion_02.ingestion_02_embedder import LegalBertEmbedder
from src.utils_03.utils_02_vector_db import VectorDatabase


class LegalRetriever:
    """Embed a question locally and retrieve its top three chunks."""

    def __init__(
        self,
        embedder: LegalBertEmbedder,
        vector_db: VectorDatabase,
    ) -> None:
        self._embedder = embedder
        self._vector_db = vector_db

    def token_count(self, question: str) -> int:
        """Return the encoder token count for input validation."""

        return self._embedder.count_tokens(question)

    def retrieve(self, question: str, law: Law) -> list[RetrievedChunk]:
        """Return usable evidence from the routed collection."""

        query_vector = self._embedder.embed_documents([question])[0]
        return usable_chunks(self._vector_db.query(law, query_vector, top_k=3))
