"""API flow 02: FastAPI entry point for PPC-PECA Lens."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from src.api_06.api_01_schemas import HealthResponse, QueryRequest, QueryResponse
from src.application_02 import build_query_service
from src.config_01 import Settings
from src.domain_01.domain_02_exceptions import (
    ConfigurationError,
    IndexNotReadyError,
    QuestionTooLongError,
    SensitiveInputError,
    UpstreamRateLimitError,
    UpstreamResponseError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from src.graph_05.graph_03_workflow import QueryService
from src.utils_03.utils_02_vector_db import VectorDatabase, read_manifest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UI_DIRECTORY = PROJECT_ROOT / "UI"


def create_app() -> FastAPI:
    """Create the API without loading the embedding model at import time."""

    # Request content must not leave through optional tracing integrations.
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    application = FastAPI(
        title="PPC-PECA Lens",
        version="0.1.0",
        description="English-only reference API for the supplied PPC and PECA PDFs.",
    )
    application.state.query_service = None
    application.state.service_lock = asyncio.Lock()

    @application.middleware("http")
    async def privacy_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    application.add_exception_handler(RequestValidationError, _validation_error)
    application.add_exception_handler(SensitiveInputError, _sensitive_input_error)
    application.add_exception_handler(QuestionTooLongError, _question_too_long_error)
    application.add_exception_handler(ConfigurationError, _service_not_ready)
    application.add_exception_handler(IndexNotReadyError, _service_not_ready)
    application.add_exception_handler(UpstreamTimeoutError, _upstream_timeout)
    application.add_exception_handler(asyncio.TimeoutError, _upstream_timeout)
    application.add_exception_handler(UpstreamResponseError, _bad_upstream_response)
    application.add_exception_handler(UpstreamRateLimitError, _upstream_unavailable)
    application.add_exception_handler(UpstreamUnavailableError, _upstream_unavailable)

    application.get("/", include_in_schema=False)(introduction_page)
    application.get("/chat", include_in_schema=False)(chat_page)
    application.get("/health", response_model=HealthResponse)(health)
    application.post("/query", response_model=QueryResponse)(query)
    application.mount("/ui", StaticFiles(directory=UI_DIRECTORY), name="ui")
    return application


async def introduction_page() -> FileResponse:
    """Serve the introduction page from the local UI directory."""

    return FileResponse(UI_DIRECTORY / "index.html", media_type="text/html")


async def chat_page() -> FileResponse:
    """Serve the session-only chat interface."""

    return FileResponse(UI_DIRECTORY / "chat.html", media_type="text/html")


async def get_query_service(request: Request) -> QueryService:
    """Build the expensive local service once and reuse it for later requests."""

    service = request.app.state.query_service
    if service is not None:
        return service
    async with request.app.state.service_lock:
        service = request.app.state.query_service
        if service is None:
            settings = Settings.from_env(require_llm=True)
            service = await asyncio.to_thread(build_query_service, settings)
            request.app.state.query_service = service
    return service


QueryServiceDependency = Annotated[QueryService, Depends(get_query_service)]


async def query(payload: QueryRequest, service: QueryServiceDependency) -> QueryResponse:
    """Answer one question without storing request state or conversation history."""

    async with asyncio.timeout(service.request_timeout_seconds):
        result = await service.ask(payload.question)
    return QueryResponse.from_result(result)


async def health() -> HealthResponse:
    """Report local index and environment readiness without calling OpenRouter."""

    try:
        settings = Settings.from_env(require_llm=False)
        configuration_ready = all(
            (
                settings.openrouter_api_key,
                settings.router_model_id,
                settings.ppc_model_id,
                settings.peca_model_id,
            )
        )
        manifest_ready = read_manifest(settings.index_manifest_path) is not None
        collections = VectorDatabase(settings.vector_db_path).collection_counts()
        index_ready = manifest_ready and all(count > 0 for count in collections.values())
    except (ConfigurationError, IndexNotReadyError, OSError, ValueError):
        configuration_ready = False
        index_ready = False
        collections = {"ppc": 0, "peca": 0}
    return HealthResponse(
        status="ready" if index_ready and configuration_ready else "not_ready",
        index_ready=index_ready,
        configuration_ready=configuration_ready,
        collections=collections,
    )


def _safe_error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


async def _validation_error(_request: Request, _exc: Exception) -> JSONResponse:
    return _safe_error(422, "Invalid request.")


async def _sensitive_input_error(_request: Request, _exc: Exception) -> JSONResponse:
    return _safe_error(422, "Remove personal identifiers before submitting the question.")


async def _question_too_long_error(_request: Request, _exc: Exception) -> JSONResponse:
    return _safe_error(422, "The question is too long for the local encoder.")


async def _service_not_ready(_request: Request, _exc: Exception) -> JSONResponse:
    return _safe_error(503, "The local service is not ready. Check configuration and ingestion.")


async def _upstream_timeout(_request: Request, _exc: Exception) -> JSONResponse:
    return _safe_error(504, "The model provider did not respond before the deadline.")


async def _bad_upstream_response(_request: Request, _exc: Exception) -> JSONResponse:
    return _safe_error(502, "The model provider returned an unusable response.")


async def _upstream_unavailable(_request: Request, _exc: Exception) -> JSONResponse:
    return _safe_error(503, "No eligible model endpoint is currently available.")


app = create_app()
