"""Utility flow 02: Chroma persistence and index compatibility checks."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.domain_01.domain_01_enums import Law
from src.domain_01.domain_02_exceptions import IndexNotReadyError
from src.domain_01.domain_03_models import DocumentChunk, RetrievedChunk


class VectorDatabase:
    """Store and retrieve the two fixed legal collections."""

    def __init__(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def reset_collections(self) -> None:
        """Delete only the two application-owned collections."""

        existing_names = {collection.name for collection in self._client.list_collections()}
        for law in Law:
            if law.value in existing_names:
                self._client.delete_collection(law.value)

    def upsert_chunks(
        self,
        law: Law,
        chunks: Sequence[DocumentChunk],
        embeddings: Sequence[Sequence[float]],
    ) -> int:
        """Idempotently write chunks using their deterministic identifiers."""

        if len(chunks) != len(embeddings):
            raise ValueError("Each chunk must have one embedding.")
        collection = self._get_or_create_collection(law)
        if chunks:
            collection.upsert(
                ids=[chunk.chunk_id for chunk in chunks],
                documents=[chunk.text for chunk in chunks],
                embeddings=[list(vector) for vector in embeddings],
                metadatas=[
                    {
                        "law": chunk.law.value,
                        "source": chunk.source,
                        "source_fingerprint": chunk.source_fingerprint,
                        "page": chunk.page,
                        "chunk_index": chunk.chunk_index,
                    }
                    for chunk in chunks
                ],
            )
        return collection.count()

    def query(
        self,
        law: Law,
        query_embedding: Sequence[float],
        *,
        top_k: int = 3,
    ) -> list[RetrievedChunk]:
        """Return the closest chunks from one legal collection."""

        existing_names = {collection.name for collection in self._client.list_collections()}
        if law.value not in existing_names:
            raise IndexNotReadyError(
                f"The {law.value} collection has not been ingested."
            )
        collection = self._client.get_collection(law.value)
        results = collection.query(
            query_embeddings=[list(query_embedding)],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        retrieved: list[RetrievedChunk] = []
        for chunk_id, text, metadata, distance in zip(
            ids, documents, metadatas, distances, strict=True
        ):
            if text is None or metadata is None or distance is None:
                continue
            retrieved.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    law=Law(str(metadata["law"])),
                    source=str(metadata["source"]),
                    page=int(metadata["page"]),
                    text=text,
                    distance=float(distance),
                )
            )
        return retrieved

    def collection_counts(self) -> dict[str, int]:
        """Return collection counts without loading the embedding model."""

        counts: dict[str, int] = {}
        existing_names = {collection.name for collection in self._client.list_collections()}
        for law in Law:
            if law.value in existing_names:
                counts[law.value] = self._client.get_collection(law.value).count()
            else:
                counts[law.value] = 0
        return counts

    def _get_or_create_collection(self, law: Law) -> Any:
        return self._client.get_or_create_collection(
            name=law.value,
            metadata={"hnsw:space": "cosine"},
        )


def read_manifest(path: Path) -> dict[str, Any] | None:
    """Read the index manifest when it exists."""

    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndexNotReadyError("The index manifest is unreadable.") from exc
    if not isinstance(value, dict):
        raise IndexNotReadyError("The index manifest has an invalid format.")
    return value


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Write the index contract after both collections succeed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def require_compatible_manifest(
    path: Path,
    expected: dict[str, Any],
) -> dict[str, Any]:
    """Reject a missing or incompatible local index."""

    actual = read_manifest(path)
    if actual is None:
        raise IndexNotReadyError("The local index has not been created.")
    for key in ("schema_version", "embedding_model", "chunk_tokens", "overlap_tokens"):
        if actual.get(key) != expected.get(key):
            raise IndexNotReadyError(
                "The local index configuration is incompatible; run ingestion with --reindex."
            )
    return actual
