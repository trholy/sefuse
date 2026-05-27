import heapq
import hmac
import os
import sys
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any

import httpx
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from data_processing.german_funding_main import run_german_funding_pipeline
from data_processing.eu_funding_main import run_eu_funding_pipeline
from shared.taxonomy_contract import taxonomy_key_set
from utils import EmbeddingService, Pipeline, QdrantManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")
_ALLOW_UNAUTHENTICATED = (
    os.getenv("ALLOW_UNAUTHENTICATED_INTERNAL_API", "").strip().lower()
    in {"1", "true", "yes", "on"}
)

if not INTERNAL_API_TOKEN:
    if _ALLOW_UNAUTHENTICATED:
        logger.warning("FastAPI is running without internal token authentication")
    else:
        logger.critical(
            "\n"
            "╔══════════════════════════════════════════════════════════════════╗\n"
            "║  STARTUP FAILED: INTERNAL_API_TOKEN is not set                  ║\n"
            "║                                                                  ║\n"
            "║  Before running docker-compose, set up your .env file:          ║\n"
            "║    1. cp .env.example .env                                       ║\n"
            "║    2. Replace all change_me_* values with real secrets           ║\n"
            "║                                                                  ║\n"
            "║  For local development without a token:                          ║\n"
            "║    Add ALLOW_UNAUTHENTICATED_INTERNAL_API=true to .env           ║\n"
            "║                                                                  ║\n"
            "║  See README.md → Security Notes for details.                     ║\n"
            "╚══════════════════════════════════════════════════════════════════╝"
        )
        sys.exit(1)
elif INTERNAL_API_TOKEN.startswith("change_me"):
    logger.critical(
        "\n"
        "╔══════════════════════════════════════════════════════════════════╗\n"
        "║  STARTUP FAILED: INTERNAL_API_TOKEN still uses a placeholder    ║\n"
        "║                                                                  ║\n"
        "║  Edit .env and replace the change_me_* value with a real secret.║\n"
        "║  See README.md → Security Notes for details.                     ║\n"
        "╚══════════════════════════════════════════════════════════════════╝"
    )
    sys.exit(1)


class InternalTokenMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that gates every request behind a shared secret.

    Reads the expected token from the ``INTERNAL_API_TOKEN`` environment
    variable. When the variable is set, every incoming request must carry
    a matching ``X-Internal-Token`` header; mismatches receive a 403
    response. Comparison uses ``hmac.compare_digest`` to avoid timing
    side-channels. When the variable is empty the middleware is a no-op,
    so local development without a token still works.

    The ``/health`` path is always exempted to allow Docker healthcheck
    probes without credentials.
    """

    async def dispatch(self, request: Request, call_next):
        """Forward the request when the token is valid; return 403 otherwise."""
        if request.url.path == "/health":
            return await call_next(request)
        if not INTERNAL_API_TOKEN:
            return await call_next(request)
        token = request.headers.get("X-Internal-Token", "")
        if not hmac.compare_digest(token, INTERNAL_API_TOKEN):
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        return await call_next(request)


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = os.getenv("MODEL", "bge-m3")
TOKENIZER = os.getenv("TOKENIZER", "BAAI/bge-m3")
OLLAMA_EMBED_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_EMBED_TIMEOUT_SECONDS", "120"))
CRON_TRIGGER_GERMAN_DATA_PROCESSING = int(os.getenv("CRON_TRIGGER_GERMAN_DATA_PROCESSING", "0"))
CRON_TRIGGER_GERMAN_EMBEDDING = int(os.getenv("CRON_TRIGGER_GERMAN_EMBEDDING", "3"))
CRON_TRIGGER_EU_DATA_PROCESSING = int(os.getenv("CRON_TRIGGER_EU_DATA_PROCESSING", "1"))
CRON_TRIGGER_EU_EMBEDDING = int(os.getenv("CRON_TRIGGER_EU_EMBEDDING", "4"))
RUN_STARTUP_PIPELINES_SYNC = (
    os.getenv("RUN_STARTUP_PIPELINES_SYNC", "false").strip().lower()
    in {"1", "true", "yes", "on"}
)
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


# ─── Request / response models ────────────────────────────────────────────────

class SearchFilters(BaseModel):
    """Optional taxonomy filters applied server-side before returning search results.

    All list fields accept human-readable taxonomy values; the backend normalises
    them to canonical keys via ``taxonomy_key_set`` before comparing. Each field
    is matched with OR within the field and AND across fields.

    Fields:
        funding_type: Allowed funding types (e.g. ``["Zuschuss"]``). None means no filter.
        funding_area: Allowed funding areas. None means no filter.
        funding_location: Allowed funding locations. None means no filter.
        eligible_applicants: Allowed applicant categories. None means no filter.
        drop_na: When True, results where both short and full description are
            ``"N/A"`` are excluded. Defaults to False.
    """

    funding_type: list[str] | None = None
    funding_area: list[str] | None = None
    funding_location: list[str] | None = None
    eligible_applicants: list[str] | None = None
    drop_na: bool = False

    @field_validator("funding_type", "funding_area", "funding_location", "eligible_applicants")
    @classmethod
    def _cap_element_length(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        return [s for s in v if len(s) <= 64][:50]


class SearchMessage(BaseModel):
    """A single chat-style message that carries the user's search query.

    Fields:
        role: Always ``"user"``; other values are rejected by Pydantic.
        content: The search query text. Must be between 1 and 5 000 characters.
    """

    role: Literal["user"] = "user"
    content: str = Field(min_length=1, max_length=5000)


class SearchRequest(BaseModel):
    """Validated request body for search endpoints.

    FastAPI automatically rejects requests that violate any constraint with a
    422 Unprocessable Entity response before the route handler is called.

    Fields:
        messages: Conversation history. Must contain 1–8 ``SearchMessage`` items;
            the first item's ``content`` is used as the search query.
        model: Ollama model name to use for query embedding (e.g. ``"bge-m3"``).
        limit: Number of results to return. Must be between 1 and 100. Defaults to 20.
        semantic_weight: Blend weight between dense (1.0) and sparse (0.0) search.
            Must be in [0.0, 1.0]. Defaults to 0.7.
        filters: Optional taxonomy filters. Defaults to an empty ``SearchFilters``
            (no filtering).
    """

    messages: list[SearchMessage] = Field(min_length=1, max_length=8)
    model: str
    limit: int = Field(ge=1, le=100, default=20)
    semantic_weight: float = Field(ge=0.0, le=1.0, default=0.7)
    filters: SearchFilters = Field(default_factory=SearchFilters)


class SearchMatch(BaseModel):
    """A single funding project result returned by the search endpoints.

    Scores are normalised to [0, 1] relative to the top result in the response.

    Fields:
        project_id: UUID of the funding project.
        project_title: Human-readable project title.
        project_short_description: Short summary of the funding program.
        project_full_description: Full description text of the funding program.
        date_1: First relevant date string (e.g. application deadline).
        date_2: Second relevant date string (e.g. funding period end).
        funding_type: Human-readable funding type labels.
        funding_area: Human-readable funding area labels.
        funding_location: Human-readable funding location labels.
        eligible_applicants: Human-readable eligible applicant labels.
        funding_type_keys: Normalised taxonomy keys for ``funding_type``.
        funding_area_keys: Normalised taxonomy keys for ``funding_area``.
        funding_location_keys: Normalised taxonomy keys for ``funding_location``.
        eligible_applicants_keys: Normalised taxonomy keys for ``eligible_applicants``.
        project_website: URL of the funding program's detail page.
        matching_score: Relevance score normalised to [0, 1].
    """

    project_id: str
    project_title: str
    project_short_description: str
    project_full_description: str
    date_1: str
    date_2: str
    funding_type: list[str]
    funding_area: list[str]
    funding_location: list[str]
    eligible_applicants: list[str]
    funding_type_keys: list[str]
    funding_area_keys: list[str]
    funding_location_keys: list[str]
    eligible_applicants_keys: list[str]
    project_website: str
    matching_score: float


class SearchResponse(BaseModel):
    """Top-level response wrapper returned by the search endpoints.

    Fields:
        matches: Ordered list of matching funding projects, sorted by descending
            ``matching_score``. Empty when no results satisfy the query and filters.
    """

    matches: list[SearchMatch]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _normalize_list_field(value: Any) -> list[Any]:
    """Wrap a scalar in a list, or return the list unchanged; None becomes []."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_filter_keys(filters: SearchFilters) -> dict[str, set[str]]:
    """Convert a SearchFilters object to normalised taxonomy key sets."""
    normalized: dict[str, set[str]] = {}
    for field in ("funding_type", "funding_area", "funding_location", "eligible_applicants"):
        raw = getattr(filters, field, None)
        keys = taxonomy_key_set(_normalize_list_field(raw))
        if keys:
            normalized[field] = keys
    return normalized


def _result_matches_filters(
    result: dict[str, Any],
    filter_keys: dict[str, set[str]],
) -> bool:
    """Return True if a result satisfies all active taxonomy filters (AND across fields)."""
    if not filter_keys:
        return True
    for field, selected_keys in filter_keys.items():
        row_keys = _normalize_list_field(result.get(f"{field}_keys"))
        normalized_row_keys = taxonomy_key_set(row_keys)
        if not normalized_row_keys.intersection(selected_keys):
            return False
    return True


TOPK_SCORES = int(os.getenv("TOPK_SCORES", "3"))


def _aggregate_results(results: list[Any]) -> list[dict[str, Any]]:
    """Deduplicate Qdrant results by project using TopK-Avg scoring.

    Multiple chunks from the same project may appear in search results. This
    function collapses them into one entry per project using ``project_uuid``
    from the point payload as the grouping key (falling back to the raw point
    ID for any point that lacks the field). The final score is the average of
    the top-K chunk scores per project.

    Args:
        results (list[Any]): Raw ``ScoredPoint`` list from ``QdrantManager.search``.

    Returns:
        list[dict[str, Any]]: Deduplicated result dicts with a ``matching_score`` field.
    """
    aggregated: Dict[str, Dict[str, Any]] = {}
    scores_by_project: Dict[str, list[float]] = {}
    for result in results:
        payload = result.payload
        if not isinstance(payload, dict):
            logger.warning(f"Skipping invalid payload: {payload}")
            continue

        project_id = payload.get("project_uuid") or str(result.id)
        if project_id not in aggregated:
            aggregated[project_id] = {
                "project_id": project_id,
                "project_title": payload.get("title") or "",
                "project_short_description": payload.get("project_short_description") or "",
                "project_full_description": payload.get("project_full_description") or "",
                "date_1": payload.get("date_1") or "",
                "date_2": payload.get("date_2") or "",
                "funding_type": _normalize_list_field(payload.get("funding_type")),
                "funding_type_keys": _normalize_list_field(payload.get("funding_type_keys")),
                "funding_area": _normalize_list_field(payload.get("funding_area")),
                "funding_area_keys": _normalize_list_field(payload.get("funding_area_keys")),
                "funding_location": _normalize_list_field(payload.get("funding_location")),
                "funding_location_keys": _normalize_list_field(payload.get("funding_location_keys")),
                "eligible_applicants": _normalize_list_field(payload.get("eligible_applicants")),
                "eligible_applicants_keys": _normalize_list_field(payload.get("eligible_applicants_keys")),
                "project_website": payload.get("url") or "",
                "matching_score": 0,
            }
            scores_by_project[project_id] = []
        scores_by_project[project_id].append(result.score)

    for project_id, entry in aggregated.items():
        top_scores = heapq.nlargest(TOPK_SCORES, scores_by_project[project_id])
        entry["matching_score"] = sum(top_scores) / len(top_scores)

    return list(aggregated.values())


OLLAMA_MODEL_READY_INTERVAL = int(os.getenv("OLLAMA_MODEL_READY_INTERVAL", "10"))
OLLAMA_MODEL_READY_TIMEOUT = int(os.getenv("OLLAMA_MODEL_READY_TIMEOUT", "600"))


async def _await_ollama_model(client: httpx.AsyncClient) -> None:
    """Block until the Ollama embedding model is ready to serve requests.

    Sends a test embed request in a loop. Retries on 404 (model still pulling)
    and connection errors. The per-request timeout uses
    ``OLLAMA_EMBED_TIMEOUT_SECONDS`` (default 120 s) so the first successful
    request can trigger GPU model load without a premature client disconnect.

    Args:
        client (httpx.AsyncClient): The shared HTTP client from ``app.state``.

    Raises:
        TimeoutError: If the model is not ready within
            ``OLLAMA_MODEL_READY_TIMEOUT`` seconds.
    """
    deadline = asyncio.get_running_loop().time() + OLLAMA_MODEL_READY_TIMEOUT
    while True:
        try:
            resp = await client.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": EMBED_MODEL, "input": "ready"},
                timeout=OLLAMA_EMBED_TIMEOUT_SECONDS,
            )
            if resp.status_code == 200:
                logger.info("Ollama model '%s' is ready", EMBED_MODEL)
                return
            logger.info(
                "Ollama returned %s — model '%s' not ready yet, retrying in %ss",
                resp.status_code, EMBED_MODEL, OLLAMA_MODEL_READY_INTERVAL,
            )
        except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException) as exc:
            logger.info(
                "Ollama not reachable (%s) — retrying in %ss",
                type(exc).__name__, OLLAMA_MODEL_READY_INTERVAL,
            )
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError(
                f"Ollama model '{EMBED_MODEL}' not ready after {OLLAMA_MODEL_READY_TIMEOUT}s"
            )
        await asyncio.sleep(OLLAMA_MODEL_READY_INTERVAL)


async def _embed_query(query: str, model: str, client: httpx.AsyncClient) -> list[float]:
    """Fetch a dense embedding vector for a search query from the Ollama API.

    Retries once on ``ConnectError``; maps all Ollama failures to a 503 so
    callers receive a structured error rather than an unhandled exception.

    Args:
        query (str): User's search text.
        model (str): Ollama model name, e.g. ``"bge-m3"``.
        client (httpx.AsyncClient): Shared HTTP client from ``app.state``.

    Returns:
        list[float]: Dense embedding vector.

    Raises:
        HTTPException: 503 when Ollama is unavailable or returns a non-2xx response.
    """
    for attempt in range(2):
        try:
            resp = await client.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": model, "input": query},
                timeout=OLLAMA_EMBED_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp.json()["embeddings"][0]
        except httpx.ConnectError:
            if attempt == 0:
                await asyncio.sleep(1)
            else:
                break
        except (httpx.HTTPStatusError, httpx.TimeoutException):
            break
    raise HTTPException(status_code=503, detail="Embedding service unavailable")


async def _search_collection(
    body: SearchRequest,
    qdrant_manager: QdrantManager,
    client: httpx.AsyncClient,
) -> Dict[str, Any]:
    """Core search handler: embed query → hybrid search → aggregate → filter → normalise.

    Pipeline:
    1. Embeds ``body.messages[0].content`` via Ollama.
    2. Runs hybrid search in ``qdrant_manager`` with ``semantic_weight``.
    3. Deduplicates chunks via ``_aggregate_results``.
    4. Normalises scores to [0, 1] by dividing by the max score.
    5. Applies taxonomy key filters and optional drop-N/A.
    6. Sorts results by descending score.

    Args:
        body (SearchRequest): Validated search request.
        qdrant_manager (QdrantManager): Collection to search against.
        client (httpx.AsyncClient): Shared HTTP client for embedding calls.

    Returns:
        dict: ``{"matches": [<result_dict>, ...]}`` ready for JSON serialisation.
    """
    query = body.messages[0].content
    model = body.model
    limit = body.limit
    semantic_weight = body.semantic_weight

    query_vector = await _embed_query(query, model, client)
    results = qdrant_manager.search(
        query_vector=query_vector,
        query_text=query,
        limit=limit * TOPK_SCORES,
        semantic_weight=semantic_weight,
    )
    aggregated = _aggregate_results(results)

    if aggregated:
        max_score = max(match["matching_score"] for match in aggregated)
        if max_score > 0:
            for match in aggregated:
                match["matching_score"] = match["matching_score"] / max_score

    filters = body.filters
    filter_keys = _normalize_filter_keys(filters)
    drop_na = filters.drop_na

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

    filtered.sort(key=lambda m: m["matching_score"], reverse=True)
    return {"matches": filtered[:limit]}


def _load_taxonomy(path: str) -> dict[str, Any]:
    """Load a taxonomy JSON artifact from disk, returning a safe empty structure on failure.

    Args:
        path (str): File path to the taxonomy JSON produced by ``TaxonomyContractBuilder``.

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
        logger.warning("Failed to load taxonomy from %s: %s", taxonomy_path, error)
        return {
            "domain": "german",
            "generated_at_utc": "",
            "version": "",
            "hash": "",
            "columns": {},
        }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown: run pipelines and schedule cron jobs.

    On startup:
    - Creates a shared ``httpx.AsyncClient`` on ``app.state``.
    - Runs German and EU data-processing pipelines in parallel with the Ollama
      model readiness probe; embedding pipelines start only after both complete.
    - Registers four APScheduler cron jobs for periodic data refresh and
      re-embedding of German and EU funding data.

    On shutdown:
    - Cancels any still-running startup background task.
    - Shuts down the APScheduler without waiting for running jobs.
    - Closes the shared HTTP client.

    Args:
        app (FastAPI): The FastAPI application instance.
    """
    loop = asyncio.get_running_loop()
    startup_task: asyncio.Task | None = None

    app.state.http_client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        timeout=OLLAMA_EMBED_TIMEOUT_SECONDS,
    )

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
        data_jobs = [
            ("German funding_data processing", run_german_data_processing),
            ("EU funding_data processing", run_eu_data_processing),
        ]
        embedding_jobs = [
            ("German embedding pipeline", run_german_embedding_pipeline),
            ("EU embedding pipeline", run_eu_embedding_pipeline),
        ]

        async def run_data_processing():
            for name, job in data_jobs:
                try:
                    await job()
                    logger.info("Startup job finished: %s", name)
                except Exception:
                    logger.exception("Startup job failed: %s", name)

        # Data processing and model readiness check run in parallel.
        # Embedding pipelines only start once both have completed.
        data_task = asyncio.create_task(run_data_processing())
        try:
            await _await_ollama_model(app.state.http_client)
        except TimeoutError:
            logger.error("Ollama model not ready — skipping embedding pipelines")
            await data_task
            return

        await data_task

        for name, job in embedding_jobs:
            try:
                await job()
                logger.info("Startup job finished: %s", name)
            except Exception:
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
    await app.state.http_client.aclose()


limiter = Limiter(key_func=get_remote_address)
scheduler = AsyncIOScheduler()
app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(InternalTokenMiddleware)

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


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Return service health: ok when both Qdrant managers have live clients."""
    if german_qdrant_manager.client is not None and eu_qdrant_manager.client is not None:
        return {"status": "ok"}
    return JSONResponse(status_code=503, content={"status": "unavailable"})


@app.post("/v1/search/german", response_model=SearchResponse)
@limiter.limit("30/minute")
async def search_projects(request: Request, body: SearchRequest) -> SearchResponse:
    """Search the German funding collection and return ranked matches.

    Rate-limited to 30 requests per minute per IP address.

    Args:
        request (Request): Starlette request (used to access ``app.state``).
        body (SearchRequest): Validated search request with query, filters, and options.

    Returns:
        SearchResponse: Ranked list of matching German funding projects.
    """
    return await _search_collection(body, german_qdrant_manager, request.app.state.http_client)


@app.post("/v1/search/eu", response_model=SearchResponse)
@limiter.limit("30/minute")
async def search_eu_projects(request: Request, body: SearchRequest) -> SearchResponse:
    """Search the EU funding collection and return ranked matches.

    Rate-limited to 30 requests per minute per IP address.

    Args:
        request (Request): Starlette request (used to access ``app.state``).
        body (SearchRequest): Validated search request with query, filters, and options.

    Returns:
        SearchResponse: Ranked list of matching EU funding projects.
    """
    return await _search_collection(body, eu_qdrant_manager, request.app.state.http_client)


@app.get("/v1/vocab/german")
@limiter.limit("120/minute")
async def get_german_taxonomy(request: Request) -> Dict[str, Any]:
    """Return the current German taxonomy contract artifact.

    Rate-limited to 120 requests per minute per IP address. Returns a blank
    skeleton instead of an error when the taxonomy file is missing or malformed.

    Args:
        request (Request): Starlette request (required by ``slowapi`` rate limiter).

    Returns:
        dict: Parsed taxonomy artifact with ``domain``, ``generated_at_utc``,
            ``version``, ``hash``, and ``columns`` keys.
    """
    return _load_taxonomy(GERMAN_TAXONOMY_FILE_PATH)
