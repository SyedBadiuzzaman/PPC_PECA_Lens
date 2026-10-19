"""Run the 20-case local retrieval and live model evaluation."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from evals.metrics import accuracy, citations_are_complete, page_hit_at_three
from src.application_02 import build_query_service
from src.config_01 import Settings
from src.core_04.core_02_retriever import LegalRetriever
from src.domain_01.domain_01_enums import Law
from src.ingestion_02.ingestion_02_embedder import LegalBertEmbedder
from src.utils_03.utils_02_vector_db import VectorDatabase

DATASET_PATH = Path("evals/datasets/test_questions.json")
RESULTS_PATH = Path("evals/results/latest.json")


async def run() -> dict[str, Any]:
    """Evaluate routing, top-three retrieval, citations, and latency."""

    settings = Settings.from_env(require_llm=True)
    cases = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    service = await asyncio.to_thread(build_query_service, settings)
    retriever = LegalRetriever(
        LegalBertEmbedder(settings.embedding_model, local_files_only=True),
        VectorDatabase(settings.vector_db_path),
    )

    route_matches: list[bool] = []
    status_matches: list[bool] = []
    retrieval_hits: list[bool] = []
    citation_checks: list[bool] = []
    latencies: list[float] = []
    details: list[dict[str, Any]] = []
    for case in cases:
        expected_law = case.get("expected_law")
        retrieved_pages: list[int] = []
        if expected_law:
            chunks = await asyncio.to_thread(
                retriever.retrieve,
                case["question"],
                Law(expected_law),
            )
            retrieved_pages = [chunk.page for chunk in chunks]
            retrieval_hits.append(
                page_hit_at_three(retrieved_pages, case["expected_pages"])
            )

        start = time.perf_counter()
        result = await service.ask(case["question"])
        latency = time.perf_counter() - start
        latencies.append(latency)
        expected_route_value = expected_law or case["expected_status"]
        actual_route_value = result.law.value if result.law else result.status.value
        route_matches.append(actual_route_value == expected_route_value)
        status_matches.append(result.status.value == case["expected_status"])
        citation_checks.append(
            citations_are_complete(result.sources, result.status.value)
        )
        details.append(
            {
                "id": case["id"],
                "expected": expected_route_value,
                "actual": actual_route_value,
                "status": result.status.value,
                "retrieved_pages": retrieved_pages,
                "cited_pages": [source.page for source in result.sources],
                "latency_seconds": round(latency, 3),
                "manual_grounding_review": None,
            }
        )

    report = {
        "case_count": len(cases),
        "routing_accuracy": accuracy(route_matches),
        "status_accuracy": accuracy(status_matches),
        "retrieval_hit_at_3": accuracy(retrieval_hits),
        "citation_validity_rate": accuracy(citation_checks),
        "mean_latency_seconds": sum(latencies) / len(latencies),
        "manual_grounding_review": "pending",
        "details": details,
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    """Run the evaluation and print aggregate metrics."""

    print(json.dumps(asyncio.run(run()), indent=2))


if __name__ == "__main__":
    main()
