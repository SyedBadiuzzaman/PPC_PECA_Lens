# Project brief

## Product

PPC-PECA Lens is an English-only backend API that provides reference answers from the two supplied Pakistan Penal Code and Prevention of Electronic Crimes Act documents. Its intended users are lawyers and citizens accessing it through a separate frontend.

The MVP is a labelled prototype. Its source files are not established as current official law: the PPC PDF says it was last amended in 2017, while the PECA PDF is headed as a bill and contains OCR errors.

## MVP outcome

The application should:

- route a standalone question to PPC or PECA;
- retrieve three local source chunks;
- return an answer only when its cited quotations can be verified locally;
- include physical PDF pages, source warnings, and a legal disclaimer;
- reject common personal identifiers before an external request; and
- retain no questions, answers, or conversation history.

Quality is measured with routing and status accuracy, retrieval hit@3, citation validity, latency, and manual grounding review. No architecture can guarantee universal 100% faithfulness or zero hallucinations.

## Required stack

- Python 3.12 and `uv`
- FastAPI, Pydantic v2, and Uvicorn
- LangChain and a stateless LangGraph workflow
- local ChromaDB collections
- local `nlpaueb/legal-bert-base-uncased` embeddings through Sentence Transformers
- OpenRouter with three required configurable model IDs: router, PPC generator, and PECA generator
- pytest for offline tests

Approved supporting packages are `python-dotenv`, `pdfplumber`, `httpx`, and `huggingface-hub` where required by Sentence Transformers.

## Outside the MVP

Frontend code, conversation history, uploads, OCR repair, Urdu support, reranking, judge models, NeMo guardrails, RAGAS/Phoenix CI, public deployment, Docker, authentication, and cloud infrastructure are outside this version.

## Acceptance criteria

- Both collections ingest idempotently and incompatible indexes require `--reindex`.
- `/health` makes no paid model call.
- `/query` returns the documented stable schema and safe HTTP errors.
- PII-pattern rejection occurs before OpenRouter is called.
- Configured model IDs have no code defaults or silent fallbacks.
- OpenRouter requests require ZDR routing and deny data collection.
- Automated tests pass without real OpenRouter calls.
- Documentation states the source, privacy, and legal limitations plainly.
