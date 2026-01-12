import time
import os
import logging
from itertools import islice
from typing import List, Optional

import httpx
import polars as pl
from transformers import AutoTokenizer

from .qdrant_utils import QdrantManager
from data_processing.main import data_processing_pipeline

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = os.getenv('MODEL', 'nomic-embed-text')
TOKENIZER = os.getenv('TOKENIZER', 'nomic-ai/nomic-embed-text-v1.5')

def download_job():
    try:
        logger.info("Triggering data processing pipeline...")
        data_processing_pipeline()
        logger.info(">>> Pipeline finished successfully")
    except Exception as e:
        logger.info(f"Pipeline failed: {e}")


def chunked(iterable, size: int):
    """Yield successive chunks of given size from iterable."""
    it = iter(iterable)
    while chunk := list(islice(it, size)):
        yield chunk


def load_funding_data(
        file_path: str,
        retries: int = 10,
        delay: int = 1
) -> pl.DataFrame:
    """Read a Parquet file with retries if the file is not ready yet."""
    for attempt in range(1, retries + 1):
        try:
            return pl.read_parquet(file_path)
        except FileNotFoundError:
            logger.info(
                f"File not found (attempt {attempt}/{retries}): {file_path}"
            )
            if attempt == retries:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 30)


class EmbeddingService:
    """Handles text embedding via Ollama using nomic-embed-text tokenizer."""

    def __init__(
            self,
            ollama_url: str = OLLAMA_URL,
            model: str = EMBED_MODEL,
            max_tokens: int = 384,
            overlap_tokens: int = 96,
            tokenizer: str = TOKENIZER
    ):
        self.ollama_url = ollama_url
        self.model = model
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

        # Tokenizer for nomic-embed-text
        self.tokenizer = AutoTokenizer.from_pretrained(
            tokenizer,
            use_fast=True
        )

    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping token-based chunks using the
        nomic-embed-text tokenizer.
        """
        tokens = self.tokenizer.encode(text, add_special_tokens=False)
        chunks = []

        start = 0
        while start < len(tokens):
            end = start + self.max_tokens
            chunk_tokens = tokens[start:end]

            chunk_text = self.tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)

            if end >= len(tokens):
                break

            start = end - self.overlap_tokens

        return chunks

    async def fetch_embedding(
        self,
        client: httpx.AsyncClient,
        text: str
    ) -> Optional[List[float]]:
        """Fetch embedding vector for a text chunk."""
        try:
            resp = await client.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=30
            )
            resp.raise_for_status()
            return resp.json().get("embedding")
        except httpx.HTTPError as e:
            logger.error(f"Embedding request failed: {e}")
            return None


class Pipeline:
    """Main pipeline to embed new rows and insert them into Qdrant."""

    def __init__(
            self,
            qdrant: QdrantManager,
            embed_service: EmbeddingService,
            file_path: str
    ):
        self.qdrant = qdrant
        self.embed_service = embed_service
        self.file_path = file_path

    async def manage_embeddings(self) -> None:
        """
        Orchestrate the full embedding management workflow for projects.

        This method loads and normalizes funding data, identifies and deletes
         removed projects from Qdrant, determines new active projects that
         require embeddings, and processes them asynchronously by generating
         and inserting embeddings for each project. Logs key steps and exits
         early if there are no new projects.
        """
        df = self._load_and_normalize_data()
        existing_ids = set(self._fetch_existing_ids())

        ids_to_delete = set(self._delete_removed_projects(df, existing_ids))

        # refresh id list
        remaining_ids = existing_ids.difference(ids_to_delete)

        new_rows = self._get_new_active_rows(df, remaining_ids)
        logger.info(f"New rows to embed: {new_rows.height}")

        if new_rows.is_empty():
            return

        await self._embed_and_insert_rows(new_rows)

    def _load_and_normalize_data(self) -> pl.DataFrame:
        """
        Load funding data from the specified file path and normalize the UUID
         column to string type.

        Returns a Polars DataFrame with all UUIDs cast to UTF-8 strings to
         ensure consistent processing in subsequent operations.
        """
        df = load_funding_data(self.file_path)
        return df.with_columns(pl.col("uuid").cast(pl.Utf8))

    def _delete_removed_projects(
            self,
            df: pl.DataFrame,
            existing_ids: set[str]
    ) -> list[str]:
        """
        Delete projects from Qdrant that are marked as deleted and exist in
         the current database.

        Identifies rows in the DataFrame where deleted is True, intersects
         their UUIDs with existing IDs, and removes any matching projects from
         Qdrant while logging the deletion count.
        """
        deleted_rows = df.filter(pl.col("deleted") == True)
        deleted_ids = set(deleted_rows["uuid"].to_list())

        ids_to_delete = list(existing_ids & deleted_ids)

        if not ids_to_delete:
            return []

        logger.info(
            f"Deleting {len(ids_to_delete)} deleted projects from Qdrant")
        self.qdrant.delete_projects(ids_to_delete)

        return ids_to_delete

    @staticmethod
    def _get_new_active_rows(
            df: pl.DataFrame,
            existing_ids: set[str],
    ) -> pl.DataFrame:
        """
        Return a DataFrame containing active projects that are not already
         in the existing IDs set.

        Filters out rows marked as deleted and excludes any projects whose UUIDs
         are present in existing_ids, resulting in only new, active projects
         to be processed for embedding.
        """
        active_rows = df.filter(pl.col("deleted") == False)

        return active_rows.filter(
            ~pl.col("uuid").is_in(existing_ids)
        )

    async def _embed_and_insert_rows(
            self,
            new_rows: pl.DataFrame
    ) -> None:
        """
        Iterate over new project rows, generate embeddings for each, and insert
         them into Qdrant.

        This method extracts descriptions, metadata, and project IDs from the
         provided DataFrame, creates a shared HTTP client, and processes each
         project sequentially by delegating to the per-project embedding pipeline.
        """
        descriptions = new_rows["description"].cast(pl.Utf8).to_list()
        metadata_list = new_rows.to_dicts()
        ids = new_rows["uuid"].to_list()

        async with httpx.AsyncClient() as client:
            for desc, meta, project_id in zip(descriptions, metadata_list, ids):
                await self._process_single_project(
                    client, desc, meta, project_id
                )

    async def _process_single_project(
            self,
            client: httpx.AsyncClient,
            description: str,
            metadata: dict,
            project_id: str,
    ) -> None:
        """
        Process a single project by chunking its description, generating
         embeddings, and storing them in Qdrant.

        The project description is split into text chunks, embeddings are
         generated asynchronously for each chunk, and all valid embeddings are
         inserted with the same metadata and project ID. If no embeddings are
         produced, the project is skipped and a warning is logged.
        """
        text_chunks = self.embed_service.chunk_text(description)

        embeddings = await self._generate_embeddings(client, text_chunks)

        if not embeddings:
            logger.warning(f"No embeddings generated for project {project_id}")
            return

        self._insert_project_embeddings(embeddings, metadata, project_id)

        logger.info(
            f"Inserted {len(embeddings)} embeddings for project {project_id}"
        )

    async def _generate_embeddings(
            self,
            client: httpx.AsyncClient,
            chunks: list[str],
    ) -> list[list[float]]:
        """
        Generate embedding vectors for a sequence of text chunks using
         the embedding service.

        Each chunk is sent asynchronously to the embedding API, and only
         successfully returned embeddings are collected and returned, preserving
         the original chunk order for all valid results.
        """
        embeddings = []

        for chunk in chunks:
            emb = await self.embed_service.fetch_embedding(client, chunk)
            if emb is not None:
                embeddings.append(emb)

        return embeddings

    def _insert_project_embeddings(
            self,
            embeddings: list[list[float]],
            metadata: dict,
            project_id: str,
    ) -> None:
        """
        Insert all embedding vectors for a single project into Qdrant using
         the same metadata and project ID.

        Each embedding in the provided list is stored as a separate vector entry,
         allowing multiple text chunks from the same project to be indexed and
         retrieved while sharing identical metadata and identifier.
        """
        for emb in embeddings:
            self.qdrant.insert_projects(
                embeddings=[emb],
                metadata_list=[metadata],
                ids=[project_id],
            )

    def _fetch_existing_ids(self) -> List[str]:
        """Fetch all existing project UUIDs from Qdrant."""
        all_ids = []
        offset = None
        try:
            while True:
                points, offset = self.qdrant.client.scroll(
                    collection_name=self.qdrant.collection_name,
                    limit=10,
                    with_payload=False,
                    with_vectors=False,
                    offset=offset,
                )
                all_ids.extend([str(p.id) for p in points])
                if offset is None:
                    break
            logger.info(f"Fetched {len(all_ids)} existing IDs from Qdrant")
        except Exception as e:
            logger.error(f"Error fetching existing IDs: {e}")
        return all_ids
