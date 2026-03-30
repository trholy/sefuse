import os
import asyncio
import logging
from typing import Dict, Any

import httpx
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from data_processing.german_funding_main import run_german_funding_pipeline
from data_processing.eu_funding_main import run_eu_funding_pipeline
from utils import EmbeddingService, Pipeline, QdrantManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = os.getenv('MODEL', 'nomic-embed-text')
TOKENIZER = os.getenv('TOKENIZER', 'nomic-ai/nomic-embed-text-v1.5')
OLLAMA_EMBED_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_EMBED_TIMEOUT_SECONDS", "120"))
CRON_TRIGGER_GERMAN_DATA_PROCESSING = int(os.getenv("CRON_TRIGGER_GERMAN_DATA_PROCESSING", "0"))
CRON_TRIGGER_GERMAN_EMBEDDING = int(os.getenv("CRON_TRIGGER_GERMAN_EMBEDDING", "3"))
CRON_TRIGGER_EU_DATA_PROCESSING = int(os.getenv("CRON_TRIGGER_EU_DATA_PROCESSING", "1"))
CRON_TRIGGER_EU_EMBEDDING = int( os.getenv("CRON_TRIGGER_EU_EMBEDDING", "4"))
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


def _normalize_list_field(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [value]


def _aggregate_results(results: list[Any]) -> list[dict[str, Any]]:
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
                "funding_area": _normalize_list_field(
                    payload.get("funding_area")
                ),
                "funding_location": _normalize_list_field(
                    payload.get("funding_location")
                ),
                "eligible_applicants": _normalize_list_field(
                    payload.get("eligible_applicants")
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
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": model, "prompt": query},
                timeout=OLLAMA_EMBED_TIMEOUT_SECONDS,
            )
        except TypeError:
            # Supports lightweight test doubles that do not accept `timeout`.
            resp = await client.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": model, "prompt": query},
            )
        resp.raise_for_status()
        return resp.json()["embedding"]


async def _search_collection(
    request: Request,
    qdrant_manager: QdrantManager,
) -> Dict[str, Any]:
    body = await request.json()
    query = body["messages"][0]["content"]
    model = body["model"]
    limit = body["limit"]

    query_vector = await _embed_query(query, model)
    results = qdrant_manager.search(query_vector, limit)

    return {"matches": _aggregate_results(results)}

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()

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

    # ---------- RUN ON STARTUP ----------
    await run_german_data_processing()
    await run_eu_data_processing()
    await run_german_embedding_pipeline()
    await run_eu_embedding_pipeline()

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

    logger.info("Shutting down scheduler")
    scheduler.shutdown(wait=False)


scheduler = AsyncIOScheduler()
app = FastAPI(lifespan=lifespan)

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
async def search_projects(request: Request) -> Dict[str, Any]:
    """Search German funding projects."""
    return await _search_collection(request, german_qdrant_manager)


@app.post("/v1/search/eu")
async def search_eu_projects(request: Request) -> Dict[str, Any]:
    """Search EU funding projects."""
    return await _search_collection(request, eu_qdrant_manager)
