"""Ingestion flow 01: load the fixed PDF corpus."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from src.domain_01.domain_01_enums import Law
from src.domain_01.domain_03_models import DocumentPage


@dataclass(frozen=True)
class DocumentSpec:
    """Physical pages selected from one source PDF."""

    law: Law
    path: Path
    first_page: int
    last_page: int


def default_document_specs(raw_directory: Path = Path("data/raw")) -> tuple[DocumentSpec, ...]:
    """Return the two source ranges approved for the prototype."""

    return (
        DocumentSpec(
            law=Law.PPC,
            path=raw_directory / "administrator92ada0936848e501425591b4ad0cd417.pdf",
            first_page=22,
            last_page=178,
        ),
        DocumentSpec(
            law=Law.PECA,
            path=raw_directory / "PECA Act Law.pdf",
            first_page=1,
            last_page=27,
        ),
    )


def source_fingerprint(path: Path) -> str:
    """Hash a source file so incompatible index contents are detected."""

    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for block in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_extracted_text(text: str) -> str:
    """Normalize layout whitespace without correcting source wording or OCR."""

    text = text.replace("\u00a0", " ").replace("\u00ad", "")
    return re.sub(r"\s+", " ", text).strip()


def load_document(spec: DocumentSpec) -> list[DocumentPage]:
    """Extract the configured physical page range from a PDF."""

    if not spec.path.is_file():
        raise FileNotFoundError(f"Source PDF not found: {spec.path}")
    fingerprint = source_fingerprint(spec.path)
    pages: list[DocumentPage] = []
    with pdfplumber.open(spec.path) as pdf:
        if spec.first_page < 1 or spec.last_page > len(pdf.pages):
            raise ValueError(
                f"Page range {spec.first_page}-{spec.last_page} is invalid for "
                f"{spec.path.name} ({len(pdf.pages)} pages)."
            )
        for physical_page in range(spec.first_page, spec.last_page + 1):
            raw_text = pdf.pages[physical_page - 1].extract_text() or ""
            normalized_text = normalize_extracted_text(raw_text)
            if not normalized_text:
                continue
            pages.append(
                DocumentPage(
                    law=spec.law,
                    source=spec.path.name,
                    source_fingerprint=fingerprint,
                    page=physical_page,
                    text=normalized_text,
                )
            )
    return pages
