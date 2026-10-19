"""Shared flow 01: environment-backed application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.domain_01.domain_02_exceptions import ConfigurationError


@dataclass(frozen=True)
class Settings:
    """Settings shared by ingestion and the API."""

    openrouter_api_key: str
    router_model_id: str
    ppc_model_id: str
    peca_model_id: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    request_timeout_seconds: float = 15.0
    upstream_timeout_seconds: float = 12.0
    embedding_model: str = "nlpaueb/legal-bert-base-uncased"
    vector_db_path: Path = Path("data/processed/chroma")
    index_manifest_path: Path = Path("data/processed/index_manifest.json")

    @classmethod
    def from_env(cls, *, require_llm: bool = True) -> "Settings":
        """Load settings without exposing secret values in errors."""

        load_dotenv(override=False)
        values = {
            "openrouter_api_key": os.getenv("OPENROUTER_API_KEY", "").strip(),
            "router_model_id": os.getenv("ROUTER_MODEL_ID", "").strip(),
            "ppc_model_id": os.getenv("PPC_MODEL_ID", "").strip(),
            "peca_model_id": os.getenv("PECA_MODEL_ID", "").strip(),
        }
        if require_llm:
            missing = [name.upper() for name, value in values.items() if not value]
            if missing:
                raise ConfigurationError(
                    "Missing required environment settings: " + ", ".join(missing)
                )

        request_timeout = _positive_float("REQUEST_TIMEOUT_SECONDS", 15.0)
        upstream_timeout = _positive_float("UPSTREAM_TIMEOUT_SECONDS", 12.0)
        if upstream_timeout >= request_timeout:
            raise ConfigurationError(
                "UPSTREAM_TIMEOUT_SECONDS must be shorter than REQUEST_TIMEOUT_SECONDS."
            )

        base_url = os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ).rstrip("/")
        if not base_url.startswith("https://"):
            raise ConfigurationError("OPENROUTER_BASE_URL must use HTTPS.")

        return cls(
            **values,
            openrouter_base_url=base_url,
            request_timeout_seconds=request_timeout,
            upstream_timeout_seconds=upstream_timeout,
            embedding_model=os.getenv(
                "EMBEDDING_MODEL", "nlpaueb/legal-bert-base-uncased"
            ),
            vector_db_path=Path(
                os.getenv("VECTOR_DB_PATH", "data/processed/chroma")
            ),
            index_manifest_path=Path(
                os.getenv(
                    "INDEX_MANIFEST_PATH", "data/processed/index_manifest.json"
                )
            ),
        )


def _positive_float(name: str, default: float) -> float:
    raw_value = os.getenv(name, str(default))
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number.") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero.")
    return value
