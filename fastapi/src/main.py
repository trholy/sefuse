import hmac
import os
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any

import httpx
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from data_processing.german_funding_main import run_german_funding_pipeline
from data_processing.eu_funding_main import run_eu_funding_pipeline
from shared.taxonomy_contract import taxonomy_key_set
from utils import EmbeddingService, Pipeline, QdrantManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")


class InternalTokenMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that gates every request behind a shared secret.

    Reads the expected token from the ``INTERNAL_API_TOKEN`` environment
    variable. When the variable is set, every incoming request must carry
    a matching ``X-Internal-Token`` header; mismatches receive a 403
    response. Comparison uses ``hmac.compare_digest`` to avoid timing
    side-channels. When the variable is empty the middleware is a no-op,
    so local development without a token still works.
    """

    async def dispatch(self, request: Request, call_next):
        """Validate the ``X-Internal-Token`` header and forward or reject the request.

        Args:
            request (Request): Incoming HTTP request.
            call_next: ASGI call chain.

        Returns:
            Response: The downstream response on success, or a 403
            ``JSONResponse`` if the token is missing or incorrect.
        """
        if not INTERNAL_API_TOKEN:
            return await call_next(request)
        token = request.headers.get("X-Internal-Token", "")
        if not hmac.compare_digest(token, INTERNAL_API_TOKEN):
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        return await call_next(request)


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = os.getenv('MODEL', 'nomic-embed-text')
TOKENIZER = os.getenv('TOKENIZER', 'nomic-ai/nomic-embed-text-v1.5')
OLLAMA_EMBED_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_EMBED_TIMEOUT_SECONDS", "120"))
CRON_TRIGGER_GERMAN_DATA_PROCESSING = int(os.getenv("CRON_TRIGGER_GERMAN_DATA_PROCESSING", "0"))
CRON_TRIGGER_GERMAN_EMBEDDING = int(os.getenv("CRON_TRIGGER_GERMAN_EMBEDDING", "3"))
CRON_TRIGGER_EU_DATA_PROCESSING = int(os.getenv("CRON_TRIGGER_EU_DATA_PROCESSING", "1"))
CRON_TRIGGER_EU_EMBEDDING = int( os.getenv("CRON_TRIGGER_EU_EMBEDDING", "4"))
RUN_STARTUP_PIPELINES_SYNC = os.getenv("RUN_STARTUP_PIPELINES_SYNC", "false",).strip().lower() in {"1", "true", "yes", "on"}
GERMAN_COLLECTION_NAME = os.getenv("GERMAN_COLLECTION_NAME", "fundings_german")
EU_COLLECTION_NAME = os.getenv("EU_COLLECTION_NAME", "fundings_eu")
GERMAN_EXTRACTED_FILE_PATH = os.getenv(
    "GERMAN_EXTRACTED_FILE_PATH",
    "data/german_parquet_data_uuid.parquet",
)
EU_EXTRACTED_FILE_PATH = os.getenv(
    "EU_EXTRACTED_FILE_PATH",
    "data/eu_parquet_data_uuid.parquet",
)
GERMAN_TAXONOMY_FILE_PATH = os.getenv(
    "GERMAN_TAXONOMY_FILE_PATH",
    "data/taxonomy_german.json",
)


class SearchMessage(BaseModel):
    content: str


class SearchRequest(BaseModel):
    messages: list[SearchMessage] = Field(min_length=1)
    model: str
    limit: int = Field(ge=1, le=100, default=20)
    semantic_weight: float = Field(ge=0.0, le=1.0, default=0.7)
    filters: dict[str, Any] = Field(default_factory=dict)


def _normalize_list_field(value: Any) -> list[Any]:
    """Wrap a scalar in a list, or return the list unchanged; None becomes [].

    Args:
        value (Any): Scalar, list, or None from a Qdrant payload field.

    Returns:
        list[Any]: Value guaranteed to be a list.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_filter_keys(filters: Any) -> dict[str, set[str]]:
    """Convert raw filter values from a request to normalised taxonomy key sets.

    Processes the four filterable taxonomy fields (`funding_type`, `funding_area`,
    `funding_location`, `eligible_applicants`). Fields absent from `filters` are skipped.

    Args:
        filters (Any): Filters dict from `SearchRequest.filters`. Non-dict input
            returns an empty dict.

    Returns:
        dict[str, set[str]]: Mapping of field name to set of normalised taxonomy keys.
    """
    if not isinstance(filters, dict):
        return {}

    normalized: dict[str, set[str]] = {}
    for field in (
        "funding_type",
        "funding_area",
        "funding_location",
        "eligible_applicants",
    ):
        keys = taxonomy_key_set(_normalize_list_field(filters.get(field)))
        if keys:
            normalized[field] = keys

    return normalized


def _result_matches_filters(
    result: dict[str, Any],
    filter_keys: dict[str, set[str]],
) -> bool:
    """Return True if a search result satisfies all active taxonomy filters.

    A result passes when, for every filtered field, at least one of its
    `<field>_keys` values intersects the requested key set (AND across fields,
    OR within each field).

    Args:
        result (dict[str, Any]): Aggregated result dict from `_aggregate_results`.
        filter_keys (dict[str, set[str]]): Normalised filter keys from
            `_normalize_filter_keys`.

    Returns:
        bool: True if the result matches all filters, or if `filter_keys` is empty.
    """
    if not filter_keys:
        return True

    for field, selected_keys in filter_keys.items():
        row_keys = _normalize_list_field(result.get(f"{field}_keys"))
        normalized_row_keys = taxonomy_key_set(row_keys)
        if not normalized_row_keys.intersection(selected_keys):
            return False

    return True


def _aggregate_results(results: list[Any]) -> list[dict[str, Any]]:
    """Deduplicate Qdrant results by project ID, keeping the highest chunk score.

    Multiple chunks from the same project may appear in search results. This
    function collapses them into one entry per `id_url` (or `result.id` as fallback),
    retaining all metadata from the first occurrence and the max score across chunks.

    Args:
        results (list[Any]): Raw `ScoredPoint` list from `QdrantManager.search`.

    Returns:
        list[dict[str, Any]]: Deduplicated result dicts with a `matching_score` field.
    """
    aggregated: Dict[str, Dict[str, Any]] = {}
    for result in results:
        payload = result.payload
        if not isinstance(payload, dict):
            logger.warning(f"Skipping invalid payload: {payload}")
            continue

        project_id = payload.get("id_url", "") or result.id
        if project_id not in aggregated:
            aggregated[project_id] = {
                "project_id": project_id,
                "project_title": payload.get("title", ""),
                "project_short_description": payload.get(
                    "project_short_description", ""
                ),
                "project_full_description": payload.get(
                    "project_full_description", ""
                ),
                "date_1": payload.get("date_1", ""),
                "date_2": payload.get("date_2", ""),
                "funding_type": _normalize_list_field(
                    payload.get("funding_type")
                ),
                "funding_type_keys": _normalize_list_field(
                    payload.get("funding_type_keys")
                ),
                "funding_area": _normalize_list_field(
                    payload.get("funding_area")
                ),
                "funding_area_keys": _normalize_list_field(
                    payload.get("funding_area_keys")
                ),
                "funding_location": _normalize_list_field(
                    payload.get("funding_location")
                ),
                "funding_location_keys": _normalize_list_field(
                    payload.get("funding_location_keys")
                ),
                "eligible_applicants": _normalize_list_field(
                    payload.get("eligible_applicants")
                ),
                "eligible_applicants_keys": _normalize_list_field(
                    payload.get("eligible_applicants_keys")
                ),
                "project_website": payload.get("url", ""),
                "matching_score": result.score,
            }
        else:
            aggregated[project_id]["matching_score"] = max(
                aggregated[project_id]["matching_score"],
                result.score,
            )

    return list(aggregated.values())


async def _embed_query(query: str, model: str) -> list[float]:
    """Fetch a dense embedding vector for a search query from the Ollama API.

    Args:
        query (str): User's search text.
        model (str): Ollama model name, e.g. `"nomic-embed-text"`.

    Returns:
        list[float]: Dense embedding vector.

    Raises:
        httpx.HTTPStatusError: If Ollama returns a non-2xx response.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": model, "prompt": query},
            timeout=OLLAMA_EMBED_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]


async def _search_collection(
    body: SearchRequest,
    qdrant_manager: QdrantManager,
) -> Dict[str, Any]:
    """Core search handler: embed query → hybrid search → aggregate → filter → normalise.

    Pipeline:
    1. Embeds `body.messages[0].content` via Ollama.
    2. Runs hybrid search in `qdrant_manager` with `semantic_weight`.
    3. Deduplicates chunks via `_aggregate_results`.
    4. Normalises scores to [0, 1] by dividing by the max score.
    5. Applies taxonomy key filters and optional drop-N/A.

    Args:
        body (SearchRequest): Validated search request (messages, model, limit,
            semantic_weight, filters).
        qdrant_manager (QdrantManager): Collection to search against.

    Returns:
        dict: `{"matches": [<result_dict>, ...]}` ready for JSON serialisation.
    """
    query = body.messages[0].content
    model = body.model
    limit = body.limit
    semantic_weight = body.semantic_weight

    query_vector = await _embed_query(query, model)
    results = qdrant_manager.search(
        query_vector=query_vector,
        query_text=query,
        limit=limit,
        semantic_weight=semantic_weight,
    )
    aggregated = _aggregate_results(results)

    if aggregated:
        max_score = max(match["matching_score"] for match in aggregated)
        if max_score > 0:
            for match in aggregated:
                match["matching_score"] = match["matching_score"] / max_score

    filters = body.filters or {}
    filter_keys = _normalize_filter_keys(filters)
    drop_na = bool(filters.get("drop_na", False))

    filtered = []
    for match in aggregated:
        if filter_keys and not _result_matches_filters(match, filter_keys):
            continue
        if drop_na:
            short = match.get("project_short_description", "")
            full = match.get("project_full_description", "")
            if short == "N/A" and full == "N/A":
                continue
        filtered.append(match)

    return {"matches": filtered}


def _load_taxonomy(path: str) -> dict[str, Any]:
    """Load a taxonomy JSON artifact from disk, returning a safe empty structure on failure.

    Args:
        path (str): File path to the taxonomy JSON produced by `TaxonomyContractBuilder`.

    Returns:
        dict: Parsed taxonomy dict, or a blank artifact skeleton if the file is
            missing or malformed.
    """
    taxonomy_path = Path(path)
    if not taxonomy_path.exists():
        return {
            "domain": "german",
            "generated_at_utc": "",
            "version": "",
            "hash": "",
            "columns": {},
        }

    try:
        return json.loads(taxonomy_path.read_text(encoding="utf-8"))
    except Exception as error:
        logger.warning(
            "Failed to load taxonomy from %s: %s",
            taxonomy_path,
            error,
        )
        return {
            "domain": "german",
            "generated_at_utc": "",
            "version": "",
            "hash": "",
            "columns": {},
        }

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    startup_task: asyncio.Task | None = None

    async def run_german_data_processing():
        logger.info("Starting German funding_data processing job")
        await loop.run_in_executor(None, run_german_funding_pipeline)

    async def run_eu_data_processing():
        logger.info("Starting EU funding_data processing job")
        await loop.run_in_executor(None, run_eu_funding_pipeline)

    async def run_german_embedding_pipeline():
        logger.info("Starting German embedding pipeline job")
        await german_pipeline.manage_embeddings()

    async def run_eu_embedding_pipeline():
        logger.info("Starting EU embedding pipeline job")
        await eu_pipeline.manage_embeddings()

    async def run_startup_pipeline() -> None:
        jobs = [
            ("German funding_data processing", run_german_data_processing),
            ("EU funding_data processing", run_eu_data_processing),
            ("German embedding pipeline", run_german_embedding_pipeline),
            ("EU embedding pipeline", run_eu_embedding_pipeline),
        ]
        for name, job in jobs:
            try:
                await job()
                logger.info("Startup job finished: %s", name)
            except Exception:
                # Keep API startup resilient even if upstream data/API is slow or unavailable.
                logger.exception("Startup job failed: %s", name)

    # ---------- RUN ON STARTUP ----------
    if RUN_STARTUP_PIPELINES_SYNC:
        logger.info("Running startup pipelines synchronously")
        await run_startup_pipeline()
    else:
        logger.info("Running startup pipelines in background task")
        startup_task = asyncio.create_task(run_startup_pipeline())

    # ---------- SCHEDULE PERIODIC JOBS ----------
    def schedule_german_data_processing():
        asyncio.run_coroutine_threadsafe(run_german_data_processing(), loop)

    def schedule_eu_data_processing():
        asyncio.run_coroutine_threadsafe(run_eu_data_processing(), loop)

    def schedule_german_embedding_pipeline():
        asyncio.run_coroutine_threadsafe(run_german_embedding_pipeline(), loop)

    def schedule_eu_embedding_pipeline():
        asyncio.run_coroutine_threadsafe(run_eu_embedding_pipeline(), loop)

    scheduler.add_job(
        schedule_german_data_processing,
        trigger=CronTrigger(hour=CRON_TRIGGER_GERMAN_DATA_PROCESSING),
        id="german_data_processing_job",
        replace_existing=True
    )

    scheduler.add_job(
        schedule_german_embedding_pipeline,
        trigger=CronTrigger(hour=CRON_TRIGGER_GERMAN_EMBEDDING),
        id="german_embedding_pipeline_job",
        replace_existing=True
    )

    scheduler.add_job(
        schedule_eu_data_processing,
        trigger=CronTrigger(hour=CRON_TRIGGER_EU_DATA_PROCESSING),
        id="eu_data_processing_job",
        replace_existing=True
    )

    scheduler.add_job(
        schedule_eu_embedding_pipeline,
        trigger=CronTrigger(hour=CRON_TRIGGER_EU_EMBEDDING),
        id="eu_embedding_pipeline_job",
        replace_existing=True
    )

    scheduler.start()
    logger.info("Scheduler started")

    yield

    if startup_task is not None and not startup_task.done():
        startup_task.cancel()

    logger.info("Shutting down scheduler")
    scheduler.shutdown(wait=False)


scheduler = AsyncIOScheduler()
app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(InternalTokenMiddleware)
taxonomy_route = app.get if hasattr(app, "get") else app.post

# Initialize services
embedding_service = EmbeddingService(tokenizer=TOKENIZER)
german_qdrant_manager = QdrantManager(collection_name=GERMAN_COLLECTION_NAME)
eu_qdrant_manager = QdrantManager(collection_name=EU_COLLECTION_NAME)
german_pipeline = Pipeline(
    german_qdrant_manager,
    embedding_service,
    GERMAN_EXTRACTED_FILE_PATH,
)
eu_pipeline = Pipeline(
    eu_qdrant_manager,
    embedding_service,
    EU_EXTRACTED_FILE_PATH,
)

@app.post("/v1/search/german")
async def search_projects(body: SearchRequest) -> Dict[str, Any]:
    """Search German funding projects."""
    return await _search_collection(body, german_qdrant_manager)


@app.post("/v1/search/eu")
async def search_eu_projects(body: SearchRequest) -> Dict[str, Any]:
    """Search EU funding projects."""
    return await _search_collection(body, eu_qdrant_manager)


@taxonomy_route("/v1/vocab/german")
async def get_german_taxonomy() -> Dict[str, Any]:
    """Return the current German taxonomy contract artifact."""
    return _load_taxonomy(GERMAN_TAXONOMY_FILE_PATH)
