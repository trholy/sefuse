import time
import os
import logging
from itertools import islice
from typing import List, Optional

import httpx
import polars as pl
from transformers import AutoTokenizer

from .qdrant_utils import QdrantManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = os.getenv('MODEL', 'nomic-embed-text')
TOKENIZER = os.getenv('TOKENIZER', 'nomic-ai/nomic-embed-text-v1.5')
OLLAMA_EMBED_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_EMBED_TIMEOUT_SECONDS", "120"))


def chunked(iterable, size: int):
    """Yield successive fixed-size chunks from an iterable.

    Args:
        iterable: Any iterable to split.
        size (int): Maximum number of elements per chunk.

    Yields:
        list: Successive sublists of at most `size` elements.
    """
    """Yield successive chunks of given size from iterable."""
    it = iter(iterable)
    while chunk := list(islice(it, size)):
        yield chunk


def load_funding_data(
        file_path: str,
        retries: int = 10,
        delay: int = 1
) -> pl.DataFrame:
    """Read a Parquet file with exponential-backoff retries.

    Retries are useful when the data-processing container writes the file
    while the FastAPI container is already attempting to read it on startup.

    Args:
        file_path (str): Path to the Parquet file.
        retries (int, default=10): Maximum number of read attempts.
        delay (int, default=1): Initial wait in seconds between attempts;
            doubles each retry up to a maximum of 30 seconds.

    Returns:
        pl.DataFrame: Loaded DataFrame.

    Raises:
        FileNotFoundError: If the file is still absent after all retries.
    """
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
    """Chunks long texts and fetches dense embeddings from the local Ollama service.

    Text is tokenised with the HuggingFace tokenizer for the configured model to
    produce overlapping chunks that respect the model's context window.

    Args:
        ollama_url (str, default=OLLAMA_URL): Base URL of the Ollama API.
        model (str, default=EMBED_MODEL): Ollama model name used for embedding.
        max_tokens (int, default=384): Maximum tokens per chunk.
        overlap_tokens (int, default=96): Token overlap between consecutive chunks.
        tokenizer (str, default=TOKENIZER): HuggingFace tokenizer identifier for
            chunk boundary calculation.

    Example:
        service = EmbeddingService()
        chunks = service.chunk_text(long_text)
        async with httpx.AsyncClient() as client:
            vector = await service.fetch_embedding(client, chunks[0])
    """

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
        """Split text into overlapping token-based chunks.

        Args:
            text (str): Input text to split.

        Returns:
            List[str]: Decoded text chunks of at most `max_tokens` tokens,
                with `overlap_tokens` overlap between adjacent chunks.
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
        """Request a dense embedding vector for a single text chunk from Ollama.

        Args:
            client (httpx.AsyncClient): Shared async HTTP client.
            text (str): Text chunk to embed.

        Returns:
            Optional[List[float]]: Embedding vector, or None if the request fails.
        """
        try:
            resp = await client.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=OLLAMA_EMBED_TIMEOUT_SECONDS
            )
            resp.raise_for_status()
            return resp.json().get("embedding")
        except httpx.HTTPError as e:
            logger.error(f"Embedding request failed: {e}")
            return None


class Pipeline:
    """Embedding pipeline: reads new Parquet rows, generates embeddings, upserts into Qdrant.

    Handles incremental updates by fetching existing IDs from Qdrant, deleting stale
    projects no longer in the Parquet, and only embedding rows not yet indexed.

    Args:
        qdrant (QdrantManager): Qdrant collection manager for insert/delete/scroll.
        embed_service (EmbeddingService): Service that chunks text and fetches embeddings.
        file_path (str): Path to the UUID Parquet file produced by `CommonDataPipeline`.

    Example:
        pipeline = Pipeline(qdrant_manager, embedding_service, "data/german_parquet_data_uuid.parquet")
        await pipeline.manage_embeddings()
    """

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
        """Run the full incremental embedding pipeline.

        Loads the Parquet file, removes stale Qdrant entries for projects
        no longer active, identifies rows not yet indexed, and embeds and
        upserts them into the Qdrant collection.
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
        """Load the Parquet file and cast the ``uuid`` column to UTF-8 strings.

        Returns:
            pl.DataFrame: DataFrame with a string-typed ``uuid`` column.
        """
        df = load_funding_data(self.file_path)
        return df.with_columns(pl.col("uuid").cast(pl.Utf8))

    def _delete_removed_projects(
            self,
            df: pl.DataFrame,
            existing_ids: set[str]
    ) -> list[str]:
        active_ids = set(
            df.filter(pl.col("deleted") == False)["uuid"].to_list()
        )
        ids_to_delete = list(existing_ids - active_ids)

        if not ids_to_delete:
            return []

        logger.info(
            f"Deleting {len(ids_to_delete)} stale projects from Qdrant"
        )
        self.qdrant.delete_projects(ids_to_delete)

        return ids_to_delete

    @staticmethod
    def _get_new_active_rows(
            df: pl.DataFrame,
            existing_ids: set[str],
    ) -> pl.DataFrame:
        """Filter the DataFrame to active rows whose UUIDs are not yet in Qdrant.

        Args:
            df (pl.DataFrame): Full funding DataFrame (includes deleted rows).
            existing_ids (set[str]): UUIDs already present in the Qdrant collection.

        Returns:
            pl.DataFrame: Subset of active, not-yet-indexed rows.
        """
        active_rows = df.filter(pl.col("deleted") == False)

        return active_rows.filter(
            ~pl.col("uuid").is_in(existing_ids)
        )

    async def _embed_and_insert_rows(
            self,
            new_rows: pl.DataFrame
    ) -> None:
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
        """Chunk, embed, and upsert a single project into Qdrant.

        Args:
            client (httpx.AsyncClient): Shared async HTTP client for Ollama requests.
            description (str): Full project description text to embed.
            metadata (dict): Payload dict stored alongside each point in Qdrant.
            project_id (str): UUID used as the Qdrant point ID.
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
        """Fetch dense embedding vectors for each text chunk from Ollama.

        Chunks that fail to embed are silently skipped.

        Args:
            client (httpx.AsyncClient): Shared async HTTP client.
            chunks (list[str]): Text chunks produced by ``EmbeddingService.chunk_text``.

        Returns:
            list[list[float]]: Successfully generated embedding vectors.
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
        self.qdrant.insert_projects(
            embeddings=embeddings,
            metadata_list=[metadata] * len(embeddings),
            ids=[project_id] * len(embeddings),
        )

    def _fetch_existing_ids(self) -> List[str]:
        """Scroll through the entire Qdrant collection and return all point IDs.

        Uses paginated scrolling (256 points per page) with no payload or
        vector data to minimise memory and network overhead.

        Returns:
            List[str]: All point IDs currently stored in the collection.
                Returns an empty list if the scroll fails.
        """
        all_ids = []
        offset = None
        try:
            while True:
                points, offset = self.qdrant.client.scroll(
                    collection_name=self.qdrant.collection_name,
                    limit=256,
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
