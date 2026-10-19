# Numbered Python file flow

The numbers make the code easier to read in sequence. They describe the logical order inside each package; Python still follows imports and function calls at runtime.

`__init__.py` and `ingestion_02/__main__.py` keep their reserved names because Python uses them to recognize packages and run `python -m src.ingestion_02`.

## Folder order

1. `domain_01/` defines shared values, errors, and data models.
2. `ingestion_02/` builds the local source index.
3. `utils_03/` provides OpenRouter and Chroma infrastructure.
4. `core_04/` contains routing, retrieval, generation, and guardrails.
5. `graph_05/` connects the runtime steps in LangGraph.
6. `api_06/` exposes the final HTTP application.

## Offline ingestion: start to end

1. `config_01.py` loads local paths and model configuration.
2. `ingestion_02/ingestion_01_loaders.py` reads and normalizes the selected PDF pages.
3. `ingestion_02/ingestion_02_embedder.py` loads the tokenizer and local embedding model.
4. `ingestion_02/ingestion_03_splitters.py` creates page-bounded chunks.
5. `utils_03/utils_02_vector_db.py` stores chunks in the PPC and PECA collections.
6. `ingestion_02/ingestion_04_command.py` coordinates the steps and writes the final manifest. This is the numbered ingestion end point.
7. `ingestion_02/__main__.py` is the reserved launcher that lets `python -m src.ingestion_02` call the numbered command.

## API request: start to end

1. `api_06/api_01_schemas.py` defines the public request and response shapes.
2. `api_06/api_02_main.py` receives `/health` and `/query` requests. This is the API entry point.
3. `config_01.py` loads configuration, and `application_02.py` constructs the services.
4. `graph_05/graph_01_state.py` defines per-request state.
5. `graph_05/graph_02_nodes.py` runs input checks, routing, retrieval, generation, and output checks.
6. `graph_05/graph_03_workflow.py` compiles and invokes the stateless workflow.
7. `core_04/core_01_router.py` chooses PPC, PECA, both, or out of scope.
8. `core_04/core_02_retriever.py` retrieves the top three local chunks.
9. `core_04/core_03_generator.py` requests a cited answer from the configured law model.
10. `core_04/guardrails_04/guardrail_01_input.py` rejects identifiers and oversized questions.
11. `core_04/guardrails_04/guardrail_02_retrieval.py` removes unusable retrieved records.
12. `core_04/guardrails_04/guardrail_03_output.py` verifies quotations and appends warnings. This is the answer-validation end point.

## Shared files

1. `domain_01/domain_01_enums.py` contains stable status and law values.
2. `domain_01/domain_02_exceptions.py` contains safe application error types.
3. `domain_01/domain_03_models.py` contains internal structured data.
4. `utils_03/utils_01_llm_client.py` contains the OpenRouter transport.
5. `utils_03/utils_02_vector_db.py` contains Chroma and manifest persistence.
