import os
import asyncio
import logging
from typing import Dict, Any

import httpx
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from data_processing.main import data_processing_pipeline
from utils import EmbeddingService, Pipeline, QdrantManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = os.getenv('MODEL', 'nomic-embed-text')
TOKENIZER = os.getenv('TOKENIZER', 'nomic-ai/nomic-embed-text-v1.5')
CRON_TRIGGER_DATA_PROCESSING = int(os.getenv('CRON_TRIGGER_DATA_PROCESSING', 0))
CRON_TRIGGER_EMBEDDING = int(os.getenv('CRON_TRIGGER_EMBEDDING', 4))
EXTRACTED_FILE_PATH = "data/parquet_data_uuid.parquet"

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()

    async def run_data_processing():
        logger.info("Starting data processing job")
        await loop.run_in_executor(None, data_processing_pipeline)

    async def run_embedding_pipeline():
        logger.info("Starting embedding pipeline job")
        await pipeline.manage_embeddings()

    # ---------- RUN ON STARTUP ----------
    await run_data_processing()
    await run_embedding_pipeline()

    # ---------- SCHEDULE PERIODIC JOBS ----------
    def schedule_data_processing():
        asyncio.run_coroutine_threadsafe(run_data_processing(), loop)

    def schedule_embedding_pipeline():
        asyncio.run_coroutine_threadsafe(run_embedding_pipeline(), loop)

    scheduler.add_job(
        schedule_data_processing,
        trigger=IntervalTrigger(minutes=1),
        #trigger=CronTrigger(hour=CRON_TRIGGER_DATA_PROCESSING),
        id="data_processing_job",
        replace_existing=True
    )

    scheduler.add_job(
        schedule_embedding_pipeline,
        trigger=IntervalTrigger(seconds=32),
        #trigger=CronTrigger(hour=CRON_TRIGGER_EMBEDDING),
        id="embedding_pipeline_job",
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
qdrant_manager = QdrantManager()
embedding_service = EmbeddingService(tokenizer=TOKENIZER)
pipeline = Pipeline(qdrant_manager, embedding_service, EXTRACTED_FILE_PATH)

@app.post("/v1/search")
async def search_projects(request: Request) -> Dict[str, Any]:
    """
    Search projects and aggregate multiple embeddings per project into
     a single result.
    """
    body = await request.json()
    query = body["messages"][0]["content"]
    model = body["model"]
    limit = body["limit"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": model, "prompt": query}
        )
        resp.raise_for_status()
        query_vector = resp.json()["embedding"]

    results = qdrant_manager.search(query_vector, limit)

    aggregated: Dict[str, Dict[str, Any]] = {}
    for r in results:
        payload = r.payload
        if not isinstance(payload, dict):
            logger.warning(f"Skipping invalid payload: {payload}")
            continue

        project_id = payload.get("id_url", "") or r.id
        if project_id not in aggregated:
            aggregated[project_id] = {
                "project_id": project_id,
                "project_title": payload.get("title", ""),
                "project_short_description": payload.get("project_short_description", ""),
                "project_full_description": payload.get("project_full_description", ""),
                "on_website_from": payload.get("on_website_from", ""),
                "last_updated": payload.get("last_updated", ""),
                "funding_type": payload.get("funding_type") if isinstance(payload.get("funding_type"), list) else [payload.get("funding_type")],
                "funding_area": payload.get("funding_area") if isinstance(payload.get("funding_area"), list) else [payload.get("funding_area")],
                "funding_location": payload.get("funding_location") if isinstance(payload.get("funding_location"), list) else [payload.get("funding_location")],
                "eligible_applicants": payload.get("eligible_applicants") if isinstance(payload.get("eligible_applicants"), list) else [payload.get("eligible_applicants")],
                "project_website": payload.get("url", ""),
                "matching_score": r.score,
            }
        else:
            # Aggregate score (take max for relevance)
            aggregated[project_id]["matching_score"] = max(aggregated[project_id]["matching_score"], r.score)

    return {"matches": list(aggregated.values())}
