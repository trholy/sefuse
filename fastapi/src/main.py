import functools
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
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from apscheduler.events import EVENT_JOB_ERROR
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from data_processing.german_funding_main import run_german_funding_pipeline
from data_processing.eu_funding_main import run_eu_funding_pipeline
from shared.gotify import verify_server
from utils import EmbeddingService, Pipeline, QdrantManager
from utils.config import (
    EMBED_MODEL,
    TOKENIZER,
    OLLAMA_EMBED_TIMEOUT_SECONDS,
)
from utils.env import read_bool, read_hour, read_int
from utils.housekeeping import run_alert_notification_cleanup, run_session_cleanup
from utils.job_runner import log_scheduler_error, make_scheduler_fn
from utils.match_levels import QueryStats
from utils.search_models import SearchFilters, SearchRequest, SearchResponse
from utils.startup_checks import validate_startup
from utils.search_service import (
    alert_scores,
    await_ollama_model,
    collection_noise_floor,
    embed_query,
    invalidate_noise_floor,
    search_collection,
)

logger = logging.getLogger(__name__)
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, _LOG_LEVEL, logging.INFO))


# Validated before anything else is built: a half-configured deployment must not
# start. These stay module attributes because InternalTokenMiddleware reads the token
# from here, and lifespan reads the other two.
_STARTUP = validate_startup()
INTERNAL_API_TOKEN = _STARTUP.internal_api_token
ALERTS_ENABLED = _STARTUP.alerts_enabled
_GOTIFY_CONFIG = _STARTUP.gotify


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
            client_host = request.client.host if request.client else "unknown"
            logger.warning(
                "Rejected request from %s — invalid token (path=%s)",
                client_host,
                request.url.path,
            )
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        return await call_next(request)


CRON_TRIGGER_GERMAN_DATA_PROCESSING = read_hour("CRON_TRIGGER_GERMAN_DATA_PROCESSING", 0)
CRON_TRIGGER_GERMAN_EMBEDDING = read_hour("CRON_TRIGGER_GERMAN_EMBEDDING", 3)
CRON_TRIGGER_EU_DATA_PROCESSING = read_hour("CRON_TRIGGER_EU_DATA_PROCESSING", 1)
CRON_TRIGGER_EU_EMBEDDING = read_hour("CRON_TRIGGER_EU_EMBEDDING", 4)
RUN_STARTUP_PIPELINES_SYNC = read_bool("RUN_STARTUP_PIPELINES_SYNC")
ALERT_CHECK_HOUR = read_hour("ALERT_CHECK_HOUR", 5)
ALERT_NOTIFICATION_RETENTION_DAYS = read_int("ALERT_NOTIFICATION_RETENTION_DAYS", 30)
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


# ─── Alert scoring (wires the module-level managers to utils.search_service) ──

async def _alert_score_fn(
    query_text: str,
    collection_type: str,
    filters: dict,
    candidate_ids: list[str],
    *,
    client: httpx.AsyncClient,
) -> tuple[list[dict[str, Any]], QueryStats]:
    """``AlertService`` scoring callback: embed the saved query, then score.

    Module-level (not inside ``lifespan``) so the same path can be run in-process
    outside the scheduler.
    """
    qdrant = german_qdrant_manager if collection_type == "german" else eu_qdrant_manager
    floor = await collection_noise_floor(qdrant, collection_type, client)
    query_vector = await embed_query(query_text, EMBED_MODEL, client)
    matches, rank_cosines = await asyncio.to_thread(
        alert_scores,
        qdrant,
        query_vector,
        candidate_ids,
        SearchFilters(**(filters or {})),
    )
    return matches, QueryStats(rank_cosines=tuple(rank_cosines), noise_floor=floor)


_EMPTY_TAXONOMY: dict[str, Any] = {
    "domain": "german",
    "generated_at_utc": "",
    "version": "",
    "hash": "",
    "columns": {},
}


@functools.lru_cache(maxsize=1)
def _load_taxonomy(path: str) -> dict[str, Any]:
    """Load a taxonomy JSON artifact from disk, returning a safe empty structure on failure.

    The result is cached (LRU, size 1) so repeated calls within the same process
    do not re-read the file.  Call ``_load_taxonomy.cache_clear()`` to invalidate
    after a pipeline run has written a new taxonomy file.

    Args:
        path (str): File path to the taxonomy JSON produced by ``TaxonomyContractBuilder``.

    Returns:
        dict: Parsed taxonomy dict, or a blank artifact skeleton if the file is
            missing or malformed.
    """
    taxonomy_path = Path(path)
    if not taxonomy_path.exists():
        return _EMPTY_TAXONOMY

    try:
        return json.loads(taxonomy_path.read_text(encoding="utf-8"))
    except Exception as error:
        logger.warning("Failed to load taxonomy from %s: %s", taxonomy_path, error)
        return _EMPTY_TAXONOMY


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

    # One lock per domain, held across both that domain's jobs. The data job rewrites
    # the parquet the embedding job reads, and their cron slots are independent — a
    # data run overrunning into the embedding slot would otherwise race it.
    german_pipeline_lock = asyncio.Lock()
    eu_pipeline_lock = asyncio.Lock()

    app.state.http_client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        timeout=OLLAMA_EMBED_TIMEOUT_SECONDS,
    )

    # Share the app-level HTTP client with the embedding pipelines so that
    # _embed_and_insert_rows reuses the existing connection pool instead of
    # creating a new one per pipeline run.
    german_pipeline.http_client = app.state.http_client
    eu_pipeline.http_client = app.state.http_client

    async def run_german_data_processing():
        async with german_pipeline_lock:
            logger.info("Starting German funding_data processing job")
            await loop.run_in_executor(None, run_german_funding_pipeline)
            _load_taxonomy.cache_clear()

    async def run_eu_data_processing():
        async with eu_pipeline_lock:
            logger.info("Starting EU funding_data processing job")
            await loop.run_in_executor(None, run_eu_funding_pipeline)

    async def _rewarm_noise_floor(qdrant, collection_type: str) -> None:
        """Re-measure a collection's canary noise floor after its embedding run.

        The floor is what both the alert levels and the interactive weak-match hint
        are judged against, and re-measuring it costs one embedding call per canary.
        Paying that here keeps it off the first search after an embedding run, which
        would otherwise wait for the whole canary set. Failures are logged and
        swallowed: an unwarmed floor degrades to "no weak-match hint", never to a
        failed search.
        """
        invalidate_noise_floor(qdrant)
        try:
            await collection_noise_floor(qdrant, collection_type, app.state.http_client)
        except Exception:
            logger.warning(
                "Could not re-warm the %s noise floor; it will be measured on demand",
                collection_type, exc_info=True,
            )

    async def run_german_embedding_pipeline():
        async with german_pipeline_lock:
            logger.info("Starting German embedding pipeline job")
            await german_pipeline.manage_embeddings()
            # New programmes can change what the alert canaries reach.
            await _rewarm_noise_floor(german_qdrant_manager, "german")

    async def run_eu_embedding_pipeline():
        async with eu_pipeline_lock:
            logger.info("Starting EU embedding pipeline job")
            await eu_pipeline.manage_embeddings()
            # New programmes can change what the alert canaries reach.
            await _rewarm_noise_floor(eu_qdrant_manager, "eu")

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
            await await_ollama_model(app.state.http_client)
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
    # The loop is the only thing the wrapper needs from this scope; bind it once so
    # the registrations below read as plain calls.
    _make_scheduler_fn = functools.partial(make_scheduler_fn, loop)

    scheduler.add_listener(log_scheduler_error, EVENT_JOB_ERROR)

    schedule_german_data_processing = _make_scheduler_fn(
        run_german_data_processing, "German funding_data processing"
    )
    schedule_eu_data_processing = _make_scheduler_fn(
        run_eu_data_processing, "EU funding_data processing"
    )
    schedule_german_embedding_pipeline = _make_scheduler_fn(
        run_german_embedding_pipeline, "German embedding pipeline"
    )
    schedule_eu_embedding_pipeline = _make_scheduler_fn(
        run_eu_embedding_pipeline, "EU embedding pipeline"
    )

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

    # ─── Session cleanup job ─────────────────────────────────────────
    scheduler.add_job(
        _make_scheduler_fn(run_session_cleanup, "session cleanup"),
        trigger=CronTrigger(hour=2),
        id="session_cleanup_job",
        replace_existing=True,
    )

    if not ALERTS_ENABLED:
        logger.info(
            "ALERTS_ENABLED is false — alert check and alert notification "
            "cleanup jobs not scheduled"
        )
    else:
        # ─── Alert notification retention job ────────────────────────
        # Runs an hour after the alert check so a night's new rows are not pruned
        # in the same pass that created them.
        scheduler.add_job(
            _make_scheduler_fn(
                functools.partial(
                    run_alert_notification_cleanup,
                    ALERT_NOTIFICATION_RETENTION_DAYS,
                ),
                "alert notification cleanup",
            ),
            trigger=CronTrigger(hour=(ALERT_CHECK_HOUR + 1) % 24),
            id="alert_notification_cleanup_job",
            replace_existing=True,
        )

        # ─── Alert check job ─────────────────────────────────────────
        async def run_alert_check():
            from utils.alert_service import AlertService

            service = AlertService(
                score_fn=functools.partial(
                    _alert_score_fn, client=app.state.http_client
                )
            )
            triggered = await service.check_all_alerts()
            logger.info("Alert check completed: %d alert(s) triggered", triggered)

        schedule_alert_check = _make_scheduler_fn(run_alert_check, "alert check")

        scheduler.add_job(
            schedule_alert_check,
            trigger=CronTrigger(hour=ALERT_CHECK_HOUR),
            id="alert_check_job",
            replace_existing=True,
        )

        # Probe the Gotify server once so an unreachable or wrong URL shows up in
        # the startup log rather than as silently missing alerts hours later. This
        # is warn-only: the server being down must not stop the search API.
        if _GOTIFY_CONFIG.enabled:
            reachable, reason = verify_server(_GOTIFY_CONFIG.base_url)
            if reachable:
                logger.info("Gotify push enabled — %s", reason)
            else:
                logger.warning("Gotify push enabled but unreachable — %s", reason)

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
eu_qdrant_manager = QdrantManager(collection_name=EU_COLLECTION_NAME, language="english")
german_pipeline = Pipeline(
    german_qdrant_manager,
    embedding_service,
    GERMAN_EXTRACTED_FILE_PATH,
    collection_type="german",
)
eu_pipeline = Pipeline(
    eu_qdrant_manager,
    embedding_service,
    EU_EXTRACTED_FILE_PATH,
    collection_type="eu",
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
    return await search_collection(
        body,
        german_qdrant_manager,
        request.app.state.http_client,
        collection_type="german",
    )


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
    return await search_collection(
        body,
        eu_qdrant_manager,
        request.app.state.http_client,
        collection_type="eu",
    )


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
