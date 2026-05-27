import asyncio
import time
import os
import logging
import uuid
from typing import List, Optional

import httpx
import polars as pl
from transformers import AutoTokenizer

from .qdrant_utils import QdrantManager

logger = logging.getLogger(__name__)


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = os.getenv('MODEL', 'bge-m3')
TOKENIZER = os.getenv('TOKENIZER', 'BAAI/bge-m3')
OLLAMA_EMBED_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_EMBED_TIMEOUT_SECONDS", "120"))
ADAPTIVE_CHUNK_THRESHOLD = int(os.getenv("ADAPTIVE_CHUNK_THRESHOLD", "600"))
EMBEDDING_CONCURRENCY = int(os.getenv("EMBEDDING_CONCURRENCY", "4"))
PAYLOAD_EXCLUDE_FIELDS = {"description"}


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
    for attempt in range(1, retries + 1):
        try:
            return pl.read_parquet(file_path)
        except Exception as exc:
            logger.info(
                "Failed to read parquet (attempt %s/%s, %s): %s",
                attempt, retries, type(exc).__name__, file_path,
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
        max_tokens (int, default=512): Maximum tokens per chunk.
        overlap_tokens (int, default=62): Token overlap between consecutive chunks.
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
            max_tokens: int = 512,
            overlap_tokens: int = 62,
            tokenizer: str = TOKENIZER
    ):
        """Initialise the embedding service and load the HuggingFace tokenizer.

        Args:
            ollama_url (str, optional): Base URL of the Ollama API.
                Defaults to the ``OLLAMA_URL`` environment variable.
            model (str, optional): Ollama model name used for embedding.
                Defaults to the ``MODEL`` environment variable.
            max_tokens (int, optional): Maximum tokens per chunk window.
                Defaults to 512.
            overlap_tokens (int, optional): Token overlap between adjacent chunks.
                Defaults to 62.
            tokenizer (str, optional): HuggingFace tokenizer identifier used to
                count tokens for chunking. Defaults to the ``TOKENIZER``
                environment variable.
        """
        self.ollama_url = ollama_url
        self.model = model
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

        self.tokenizer = AutoTokenizer.from_pretrained(
            tokenizer,
            use_fast=True
        )

    def chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping token-based chunks.

        Short documents (≤ ADAPTIVE_CHUNK_THRESHOLD tokens) are returned as a
        single chunk to avoid semantically impoverished tail fragments.
        Non-final chunks are trimmed to the last sentence boundary in their
        trailing quarter to prevent mid-sentence splits.

        Args:
            text (str): Input text to split.

        Returns:
            List[str]: Decoded text chunks of at most `max_tokens` tokens,
                with `overlap_tokens` overlap between adjacent chunks.
        """
        tokens = self.tokenizer.encode(text, add_special_tokens=False)

        if len(tokens) <= ADAPTIVE_CHUNK_THRESHOLD:
            return [text]

        chunks = []

        start = 0
        while start < len(tokens):
            end = start + self.max_tokens
            chunk_tokens = tokens[start:end]

            decoded = self.tokenizer.decode(chunk_tokens)

            if end < len(tokens):
                three_quarter = (end - start) * 3 // 4
                min_keep_chars = len(self.tokenizer.decode(tokens[start : start + three_quarter]))
                decoded = self._snap_to_sentence(decoded, min_keep_chars)

            chunks.append(decoded)

            if end >= len(tokens):
                break

            start = end - self.overlap_tokens

        return chunks

    @staticmethod
    def _snap_to_sentence(text: str, min_keep_chars: int) -> str:
        """Trim text to the last sentence boundary after `min_keep_chars`.

        Searches the region beyond `min_keep_chars` for sentence-ending markers
        (``. ``, ``? ``, ``! `` and their newline variants) and truncates at the
        last one found. If no boundary exists, the text is returned unchanged.

        `min_keep_chars` is computed by the caller from the 75% token boundary,
        so the cut-off aligns with token space rather than character space.

        Args:
            text (str): Decoded chunk text to trim.
            min_keep_chars (int): Minimum number of characters to preserve;
                derived from decoding the first 75% of the chunk's tokens.

        Returns:
            str: Text truncated at the last sentence boundary, or the
                original text if no boundary is found after `min_keep_chars`.
        """
        search_region = text[min_keep_chars:]
        best = -1
        for marker in (". ", "? ", "! ", ".\n", "?\n", "!\n"):
            pos = search_region.rfind(marker)
            if pos > best:
                best = pos
        if best >= 0:
            return text[:min_keep_chars + best + 1]
        return text

    async def fetch_embeddings_batch(
        self,
        client: httpx.AsyncClient,
        texts: List[str],
    ) -> List[Optional[List[float]]]:
        """Request dense embedding vectors for a batch of texts in one Ollama call.

        Sends a single POST to ``/api/embed`` with all texts as the ``input`` list.
        Returns vectors in the same order as ``texts``; failed requests yield ``None``
        at the corresponding index.

        Args:
            client (httpx.AsyncClient): Shared async HTTP client.
            texts (List[str]): Texts to embed in one request.

        Returns:
            List[Optional[List[float]]]: Embedding vectors, one per input text.
                ``None`` at an index means that embedding failed.
        """
        try:
            resp = await client.post(
                f"{self.ollama_url}/api/embed",
                json={"model": self.model, "input": texts},
                timeout=OLLAMA_EMBED_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings", [])
            result: List[Optional[List[float]]] = list(embeddings)
            result += [None] * (len(texts) - len(result))
            return result
        except httpx.HTTPError as e:
            logger.error(f"Batch embedding request failed: {e}")
            return [None] * len(texts)

    async def fetch_embedding(
        self,
        client: httpx.AsyncClient,
        text: str
    ) -> Optional[List[float]]:
        """Request a dense embedding vector for a single text chunk from Ollama.

        Thin wrapper around ``fetch_embeddings_batch`` for single-text callers.

        Args:
            client (httpx.AsyncClient): Shared async HTTP client.
            text (str): Text chunk to embed.

        Returns:
            Optional[List[float]]: Embedding vector, or None if the request fails.
        """
        results = await self.fetch_embeddings_batch(client, [text])
        return results[0]


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
        """Store references to the Qdrant manager, embedding service, and data file path.

        Args:
            qdrant (QdrantManager): Qdrant collection manager for insert/delete/scroll.
            embed_service (EmbeddingService): Service that chunks text and fetches embeddings.
            file_path (str): Path to the UUID Parquet file produced by ``CommonDataPipeline``.
        """
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
        existing_ids = set(self._fetch_existing_project_ids())

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
        """Delete Qdrant points for projects no longer active in the Parquet file.

        Computes the set difference between ``existing_ids`` and the UUIDs of
        active (non-deleted) rows in ``df``, then removes the stale points from
        the Qdrant collection.

        Args:
            df (pl.DataFrame): Full funding DataFrame including deleted rows.
            existing_ids (set[str]): Project UUIDs currently indexed in Qdrant.

        Returns:
            list[str]: UUIDs that were deleted from Qdrant (empty if nothing to delete).
        """
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
        """Embed and upsert all rows in ``new_rows`` into Qdrant with bounded concurrency.

        Builds one async task per project and runs them concurrently, gated by
        an ``asyncio.Semaphore`` of size ``EMBEDDING_CONCURRENCY`` to avoid
        overwhelming the Ollama API.

        Args:
            new_rows (pl.DataFrame): Active, not-yet-indexed rows to process.
        """
        descriptions = new_rows["description"].cast(pl.Utf8).to_list()
        metadata_list = new_rows.to_dicts()
        ids = new_rows["uuid"].to_list()

        semaphore = asyncio.Semaphore(EMBEDDING_CONCURRENCY)

        async def _bounded(client: httpx.AsyncClient, desc: str, meta: dict, pid: str) -> None:
            async with semaphore:
                await self._process_single_project(client, desc, meta, pid)

        async with httpx.AsyncClient(
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            timeout=OLLAMA_EMBED_TIMEOUT_SECONDS,
        ) as client:
            await asyncio.gather(*(
                _bounded(client, desc, meta, pid)
                for desc, meta, pid in zip(descriptions, metadata_list, ids)
            ))

    async def _process_single_project(
            self,
            client: httpx.AsyncClient,
            description: str,
            metadata: dict,
            project_id: str,
    ) -> None:
        """Chunk, embed, and upsert a single project into Qdrant.

        Each chunk gets a unique point ID (``{project_id}_chunk_{i}``), a
        contextual header (title + funding area). The enriched chunk text is
        passed separately for sparse vector construction.

        Args:
            client (httpx.AsyncClient): Shared async HTTP client for Ollama requests.
            description (str): Full project description text to embed.
            metadata (dict): Payload dict stored alongside each point in Qdrant.
            project_id (str): UUID used as the base for Qdrant point IDs.
        """
        text_chunks = self.embed_service.chunk_text(description)

        title = metadata.get("title", "N/A")
        funding_area = metadata.get("funding_area", [])
        if isinstance(funding_area, list) and funding_area:
            area_str = ", ".join(str(a) for a in funding_area)
            header = f"Title: {title}\nFunding area: {area_str}\n\n"
        else:
            header = f"Title: {title}\n\n"

        enriched_chunks = [f"{header}{chunk}" for chunk in text_chunks]

        embeddings_batch = await self.embed_service.fetch_embeddings_batch(client, enriched_chunks)
        indexed_embeddings = [
            (i, emb) for i, emb in enumerate(embeddings_batch) if emb is not None
        ]

        if not indexed_embeddings:
            logger.warning(f"No embeddings generated for project {project_id}")
            return

        project_ns = uuid.UUID(project_id)
        chunk_ids = [str(uuid.uuid5(project_ns, f"chunk_{i}")) for i, _ in indexed_embeddings]
        embeddings = [emb for _, emb in indexed_embeddings]
        chunk_texts = [enriched_chunks[i] for i, _ in indexed_embeddings]

        chunk_metadata = []
        for i, _ in indexed_embeddings:
            meta = {k: v for k, v in metadata.items() if k not in PAYLOAD_EXCLUDE_FIELDS}
            meta["project_uuid"] = project_id
            meta["chunk_index"] = i
            chunk_metadata.append(meta)

        self.qdrant.insert_projects(
            embeddings=embeddings,
            metadata_list=chunk_metadata,
            ids=chunk_ids,
            chunk_texts=chunk_texts,
        )

        logger.info(
            f"Inserted {len(indexed_embeddings)} chunks for project {project_id}"
        )

    def _fetch_existing_project_ids(self) -> list[str]:
        """Scroll the Qdrant collection and return unique project UUIDs.

        Reads the ``project_uuid`` payload field from each point. For legacy
        points that lack this field (pre-migration), the point ID itself is
        used as a fallback.

        Returns:
            list[str]: Deduplicated project UUIDs currently indexed.

        Raises:
            Exception: Propagates any Qdrant scroll error so callers can abort
                the embedding run rather than silently treating the collection
                as empty.
        """
        project_ids: set[str] = set()
        offset = None
        while True:
            points, offset = self.qdrant.client.scroll(
                collection_name=self.qdrant.collection_name,
                limit=256,
                with_payload=["project_uuid"],
                with_vectors=False,
                offset=offset,
            )
            for p in points:
                if p.payload and "project_uuid" in p.payload:
                    project_ids.add(p.payload["project_uuid"])
                else:
                    project_ids.add(str(p.id))
            if offset is None:
                break
        logger.info(f"Fetched {len(project_ids)} existing project IDs from Qdrant")
        return list(project_ids)
