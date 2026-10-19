"""Shared flow 02: composition root for the local RAG services."""

from __future__ import annotations

from src.config_01 import Settings
from src.core_04.core_01_router import LegalRouter
from src.core_04.core_02_retriever import LegalRetriever
from src.core_04.core_03_generator import LegalGenerator
from src.domain_01.domain_02_exceptions import IndexNotReadyError
from src.graph_05.graph_02_nodes import GraphNodes
from src.graph_05.graph_03_workflow import QueryService, compile_graph
from src.ingestion_02.ingestion_01_loaders import default_document_specs, source_fingerprint
from src.ingestion_02.ingestion_02_embedder import LegalBertEmbedder
from src.ingestion_02.ingestion_03_splitters import CHUNK_OVERLAP_TOKENS, CHUNK_TOKENS
from src.utils_03.utils_01_llm_client import OpenRouterClient
from src.utils_03.utils_02_vector_db import (
    VectorDatabase,
    require_compatible_manifest,
)


def build_query_service(settings: Settings) -> QueryService:
    """Validate local resources and compose the stateless query service."""

    expected_manifest = {
        "schema_version": 1,
        "embedding_model": settings.embedding_model,
        "chunk_tokens": CHUNK_TOKENS,
        "overlap_tokens": CHUNK_OVERLAP_TOKENS,
    }
    manifest = require_compatible_manifest(
        settings.index_manifest_path,
        expected_manifest,
    )
    try:
        current_fingerprints = {
            spec.law.value: source_fingerprint(spec.path)
            for spec in default_document_specs()
        }
    except OSError as exc:
        raise IndexNotReadyError("A source PDF is unavailable.") from exc
    if manifest.get("source_fingerprints") != current_fingerprints:
        raise IndexNotReadyError(
            "The source PDFs differ from the indexed files; run ingestion with --reindex."
        )

    vector_db = VectorDatabase(settings.vector_db_path)
    if any(count <= 0 for count in vector_db.collection_counts().values()):
        raise IndexNotReadyError("Both legal collections must contain indexed chunks.")
    try:
        embedder = LegalBertEmbedder(settings.embedding_model, local_files_only=True)
    except (OSError, RuntimeError) as exc:
        raise IndexNotReadyError(
            "The local embedding model is unavailable; run ingestion first."
        ) from exc
    client = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        timeout_seconds=settings.upstream_timeout_seconds,
    )
    nodes = GraphNodes(
        router=LegalRouter(client, settings.router_model_id),
        retriever=LegalRetriever(embedder, vector_db),
        generator=LegalGenerator(
            client,
            ppc_model_id=settings.ppc_model_id,
            peca_model_id=settings.peca_model_id,
        ),
    )
    return QueryService(
        compile_graph(nodes),
        request_timeout_seconds=settings.request_timeout_seconds,
    )
