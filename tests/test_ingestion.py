"""White-box and integration tests for ingestion."""

import re
from pathlib import Path

from src.domain_01.domain_01_enums import Law
from src.domain_01.domain_02_exceptions import IndexNotReadyError
from src.domain_01.domain_03_models import DocumentChunk, DocumentPage
from src.ingestion_02.ingestion_01_loaders import (
    DocumentSpec,
    load_document,
    normalize_extracted_text,
)
from src.ingestion_02.ingestion_03_splitters import split_page
from src.utils_03.utils_02_vector_db import (
    VectorDatabase,
    require_compatible_manifest,
    write_manifest,
)


class WordTokenizer:
    """Small deterministic tokenizer used only by splitter tests."""

    def offsets_for_chunking(self, text: str) -> list[tuple[int, int]]:
        return [(match.start(), match.end()) for match in re.finditer(r"\S+", text)]


def test_normalize_extracted_text_preserves_wording() -> None:
    raw = "Section\u00a03\n  unautho\u00adrized   access"
    assert normalize_extracted_text(raw) == "Section 3 unauthorized access"


def test_split_page_stays_within_page_and_overlaps() -> None:
    page = DocumentPage(
        law=Law.PPC,
        source="ppc.pdf",
        source_fingerprint="fingerprint",
        page=22,
        text="zero one two three four five six",
    )
    chunks = split_page(page, WordTokenizer(), chunk_tokens=4, overlap_tokens=1)

    assert [chunk.text for chunk in chunks] == [
        "zero one two three",
        "three four five six",
    ]
    assert all(chunk.page == 22 for chunk in chunks)
    assert chunks[0].chunk_id != chunks[1].chunk_id


def test_split_page_rejects_invalid_overlap() -> None:
    page = DocumentPage(Law.PPC, "x.pdf", "hash", 1, "text")
    try:
        split_page(page, WordTokenizer(), chunk_tokens=4, overlap_tokens=4)
    except ValueError as exc:
        assert "overlap_tokens" in str(exc)
    else:
        raise AssertionError("Expected invalid overlap to fail.")


def test_load_document_uses_physical_page_metadata() -> None:
    spec = DocumentSpec(
        law=Law.PPC,
        path=Path("data/raw/administrator92ada0936848e501425591b4ad0cd417.pdf"),
        first_page=22,
        last_page=22,
    )
    pages = load_document(spec)

    assert len(pages) == 1
    assert pages[0].page == 22
    assert pages[0].source == spec.path.name
    assert "PAKISTAN PENAL CODE" in pages[0].text


def test_chroma_upsert_is_idempotent(tmp_path: Path) -> None:
    database = VectorDatabase(tmp_path / "chroma")
    chunks = [
        DocumentChunk("one", Law.PPC, "ppc.pdf", "hash", 22, 0, "first"),
        DocumentChunk("two", Law.PPC, "ppc.pdf", "hash", 22, 1, "second"),
    ]
    embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]

    assert database.upsert_chunks(Law.PPC, chunks, embeddings) == 2
    assert database.upsert_chunks(Law.PPC, chunks, embeddings) == 2


def test_incompatible_manifest_requires_reindex(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    write_manifest(
        manifest_path,
        {
            "schema_version": 1,
            "embedding_model": "old-model",
            "chunk_tokens": 384,
            "overlap_tokens": 48,
        },
    )

    try:
        require_compatible_manifest(
            manifest_path,
            {
                "schema_version": 1,
                "embedding_model": "new-model",
                "chunk_tokens": 384,
                "overlap_tokens": 48,
            },
        )
    except IndexNotReadyError as exc:
        assert "--reindex" in str(exc)
    else:
        raise AssertionError("Expected an incompatible manifest to fail.")
