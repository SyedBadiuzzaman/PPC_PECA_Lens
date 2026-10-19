"""Ingestion flow 04: coordinate and build the local indexes."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.config_01 import Settings
from src.domain_01.domain_03_models import DocumentChunk
from src.ingestion_02.ingestion_01_loaders import (
    default_document_specs,
    load_document,
    source_fingerprint,
)
from src.ingestion_02.ingestion_02_embedder import LegalBertEmbedder
from src.ingestion_02.ingestion_03_splitters import (
    CHUNK_OVERLAP_TOKENS,
    CHUNK_TOKENS,
    split_page,
)
from src.utils_03.utils_02_vector_db import VectorDatabase, read_manifest, write_manifest

SCHEMA_VERSION = 1


def build_index(*, reindex: bool = False, raw_directory: Path = Path("data/raw")) -> dict[str, int]:
    """Build both collections and return their final chunk counts."""

    settings = Settings.from_env(require_llm=False)
    specs = default_document_specs(raw_directory)
    embedder = LegalBertEmbedder(settings.embedding_model, local_files_only=False)
    vector_db = VectorDatabase(settings.vector_db_path)

    source_fingerprints = {
        spec.law.value: source_fingerprint(spec.path) for spec in specs
    }
    source_contract = {
        spec.law.value: {
            "filename": spec.path.name,
            "first_page": spec.first_page,
            "last_page": spec.last_page,
        }
        for spec in specs
    }
    contract = {
        "schema_version": SCHEMA_VERSION,
        "embedding_model": settings.embedding_model,
        "embedding_dimension": embedder.dimension,
        "chunk_tokens": CHUNK_TOKENS,
        "overlap_tokens": CHUNK_OVERLAP_TOKENS,
        "sources": source_contract,
        "source_fingerprints": source_fingerprints,
    }
    existing = read_manifest(settings.index_manifest_path)
    if existing is not None and not reindex:
        comparable_keys = (
            "schema_version",
            "embedding_model",
            "embedding_dimension",
            "chunk_tokens",
            "overlap_tokens",
            "sources",
            "source_fingerprints",
        )
        if any(existing.get(key) != contract.get(key) for key in comparable_keys):
            raise RuntimeError(
                "The existing index is incompatible. Re-run with --reindex to replace it."
            )
    if reindex:
        vector_db.reset_collections()
        settings.index_manifest_path.unlink(missing_ok=True)

    counts: dict[str, int] = {}
    for spec in specs:
        pages = load_document(spec)
        chunks: list[DocumentChunk] = []
        for page in pages:
            chunks.extend(split_page(page, embedder))
        embeddings = embedder.embed_documents([chunk.text for chunk in chunks])
        counts[spec.law.value] = vector_db.upsert_chunks(spec.law, chunks, embeddings)

    write_manifest(
        settings.index_manifest_path,
        {**contract, "chunk_counts": counts},
    )
    return counts


def main() -> None:
    """Parse command-line options and build the local index."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Replace incompatible or stale PPC and PECA collections.",
    )
    args = parser.parse_args()
    counts = build_index(reindex=args.reindex)
    print(f"Index ready: PPC={counts['ppc']} chunks, PECA={counts['peca']} chunks")


if __name__ == "__main__":
    main()
