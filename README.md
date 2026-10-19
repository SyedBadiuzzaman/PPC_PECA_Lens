# PPC-PECA Lens

**An English legal-reference prototype that shows where an answer came from.** Ask about the two supplied Pakistan Penal Code (PPC) and PECA PDFs, then inspect the quoted passages and physical PDF pages behind the response. The application runs locally with a two-page browser interface and a FastAPI backend.

> [!WARNING]
> **Use this as a reference, not legal advice.** The supplied PPC PDF says it was last amended on 16 February 2017. The supplied PECA PDF is headed as a bill and contains visible OCR errors. Neither document establishes the current law; verify important points against current official sources.

## How the data moves

![Animated data flow: supplied PPC and PECA PDFs become local page chunks and Chroma indexes; each browser question is checked, routed, retrieved, generated, and citation-checked before the response appears.](ui/data-flow.svg)

[Open the full-size diagram](ui/data-flow.svg). Its moving connectors indicate direction; the labels and arrows remain readable when animation is unavailable or reduced motion is enabled.

The diagram has two independent paths:

1. **Prepare sources offline:** `pdfplumber` reads selected physical pages, the text is split within each page, Legal-BERT creates local embeddings, and Chroma stores separate PPC and PECA collections plus an index manifest.
2. **Answer one question:** the browser sends a standalone question to FastAPI. Local checks reject invalid or recognizable sensitive input. An OpenRouter model selects one law; the application retrieves three chunks from that law's local collection. A configured generator drafts a response, and local checks accept only references and quotations found in those retrieved chunks.

The browser shows `status`, `law`, `answer`, `sources`, and `warnings`. It keeps visible turns only in the open page. No earlier turn is sent with a later question.

## What you can do

- Read the introduction at `/` and ask questions at `/chat` on phone or laptop.
- Inspect an answer's source filename, physical page, chunk ID, and verified quotation.
- See clarification, out-of-scope, missing-evidence, readiness, validation, and provider-error states.
- Start a new visible session without retaining the previous transcript.
- Call the same backend directly through `GET /health` and `POST /query`.

## Run locally

Use **Python 3.12**, [`uv`](https://docs.astral.sh/uv/), the two PDFs already in `data/raw/`, and Internet access for dependency/model setup and OpenRouter requests. Run these commands from the repository root in PowerShell.

1. Install the dependencies recorded in `uv.lock`:

   ```powershell
   uv sync --python 3.12 --dev
   ```

2. Create `.env` and fill in all four required values:

   ```powershell
   Copy-Item .env.example .env
   ```

   ```dotenv
   OPENROUTER_API_KEY=your-key
   ROUTER_MODEL_ID=provider/router-model
   PPC_MODEL_ID=provider/ppc-generator
   PECA_MODEL_ID=provider/peca-generator
   ```

   Select model IDs available to your OpenRouter account. The application supplies no model-ID defaults or automatic substitutes. Keep `.env` private; it is excluded by `.gitignore`. Optional paths and timeouts are listed in [.env.example](.env.example).

3. Build the local index. The first run downloads `nlpaueb/legal-bert-base-uncased` and ingests PPC physical pages **22–178** and PECA physical pages **1–27**:

   ```powershell
   uv run python -m src.ingestion_02
   ```

   Re-running ingestion uses deterministic chunk IDs. If the source or embedding configuration changes, rebuild deliberately with `uv run python -m src.ingestion_02 --reindex`. The Chroma collections and manifest are stored under `data/processed/`.

4. Start FastAPI on localhost:

   ```powershell
   uv run uvicorn src.api_06.api_02_main:app --host 127.0.0.1 --port 8000
   ```

5. Open [the introduction](http://127.0.0.1:8000/) or go directly to [the chat](http://127.0.0.1:8000/chat). The chat checks readiness before enabling the question box. Press **Enter** to send; use **Shift+Enter** for a new line. **New session**, reload, navigation away, and tab closure discard the visible transcript.

In WSL, use `cp .env.example .env` in step 2. The `uv` and server commands remain the same.

### Check the API directly

`/health` checks local configuration and index readiness without making a paid model call:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

The response reports `status`, `index_ready`, `configuration_ready`, and collection counts. A `not_ready` result means the chat remains unavailable until configuration and ingestion are complete.

Send one question from PowerShell:

```powershell
$body = @{ question = "How does the PPC define theft?" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/query -ContentType application/json -Body $body
```

Query result payloads contain `status`, `law`, `answer`, `sources`, and `warnings`. Status is one of `answered`, `insufficient_context`, `needs_clarification`, or `out_of_scope`. An answered result includes source entries with the law, filename, physical page, chunk ID, and quotation. Each query result includes a legal disclaimer. Input failures return a sanitized **422**; unusable provider responses return **502**; unavailable configuration, index, or eligible model endpoint returns **503**; and timeouts return **504**.

## Test and evaluate

The offline test suite mocks OpenRouter and does not use API credit:

```powershell
uv run pytest
```

If Node.js is installed, check the plain JavaScript syntax with `node --check ui/app.js`. The frontend has no build step or third-party browser packages.

After setup and ingestion, run the 20-case live evaluation:

```powershell
uv run python -m evals.run_evals
```

Live evaluation needs configured model IDs and a funded API key. It reports routing and status accuracy, retrieval hit@3, citation validity, and latency. `manual_grounding_review` remains a human task: matching a quote does not establish that the answer is complete or legally correct.

## Technology and project map

| Part | Purpose |
| --- | --- |
| Plain HTML, CSS, JavaScript | Responsive introduction and session-only chat in `ui/` |
| FastAPI + Pydantic | Same-origin pages and validated `/health` and `/query` API |
| `pdfplumber` + Sentence Transformers / Legal-BERT | PDF extraction and local text embeddings |
| ChromaDB | Separate local PPC and PECA vector collections |
| LangGraph + LangChain messages | Stateless, linear request workflow |
| `httpx` + OpenRouter | Async routing and generation requests |

The numbered Python folders in `src/` group ingestion, domain models, utilities, core logic, graph nodes, and API routes. See [ARCHITECTURE.md](ARCHITECTURE.md) for component boundaries and [src/FLOW.md](src/FLOW.md) for the numbered file order.

## Privacy and limits

- Questions, answers, browser transcripts, prompt caches, and LangGraph checkpoints are not persisted by the application. The browser uses no cookies, local storage, session storage, or analytics.
- Basic checks reject recognizable emails, Pakistani CNICs, and phone numbers before an external call. They can miss names and other personal information; do not submit private case details.
- OpenRouter requests ask for zero-data-retention routing and deny data collection. These are provider policy controls, not an independently verified deletion guarantee. A model without an eligible endpoint is reported as unavailable.
- Citation checks confirm that a quoted string appears in a retrieved chunk. They cannot prove legal reasoning, completeness, or current law.
- The documented server binds to `127.0.0.1`. This prototype has no authentication or application rate limiter and is not configured for public deployment.

The English-only prototype does not yet include Urdu retrieval, corrected OCR or current official sources, reranking, a judge model, uploads, or public deployment controls.

## License

No license has been selected. Ask the project owner before reusing or publishing the code under an open-source license.
#   P P C _ P E C A _ L e n s  
 