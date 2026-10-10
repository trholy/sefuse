import asyncio
import hashlib
import json
import time
import os
import logging
import uuid
from typing import Any, Dict, List, Optional

import httpx
import polars as pl
from transformers import AutoTokenizer

from .config import (
    OLLAMA_URL,
    EMBED_MODEL,
    TOKENIZER,
    OLLAMA_EMBED_TIMEOUT_SECONDS,
    PAYLOAD_EXCLUDE_FIELDS,
    PAYLOAD_DISPLAY_FIELDS,
    PAYLOAD_LIST_FIELDS,
    FIRST_SEEN_BURST_MIN,
    FIRST_SEEN_BURST_RATIO,
    DUPLICATE_COSINE,
)
from .first_seen import fetch_known_ids, mark_duplicates, record_first_seen
from .qdrant_utils import QdrantManager

logger = logging.getLogger(__name__)


ADAPTIVE_CHUNK_THRESHOLD = int(os.getenv("ADAPTIVE_CHUNK_THRESHOLD", "600"))
EMBEDDING_CONCURRENCY = int(os.getenv("EMBEDDING_CONCURRENCY", "4"))

# `DataCleaner` fills every missing string with this literal before the data is
# written, so a field that says "N/A" is an absent field, not a value. Embedding it
# would put the same meaningless token into thousands of documents.
PLACEHOLDER_VALUE = "N/A"

# Fields prepended to every chunk before it is embedded, as (metadata key, label)
# pairs in header order. `description` is not here — it is the chunked body.
#
# The header is repeated on each chunk so that a chunk taken from the middle of a
# long programme still carries what it is about. Keep it short for that reason: at
# ~115 tokens it already costs a fifth of the 512-token window, and every field
# added is paid for on every chunk of every project.
CONTEXT_HEADER_FIELDS: tuple[tuple[str, str], ...] = (
    ("title", "Title"),
    ("funding_type", "Funding type"),
    ("funding_area", "Funding area"),
    ("eligible_applicants", "Eligible applicants"),
    ("keywords_extracted", "Keywords"),
    ("project_short_description", "Summary"),
)

# Per-collection caps on how many list elements a header field contributes to the
# *embedded* text. EU calls are tagged from a far broader vocabulary than German
# programmes: the list is 6 areas at the median and 19 at p90, but the worst carries
# 213, which put a 1_591-token header on every 512-token chunk — about 78% of those
# chunks' tokens. The cap is set at p90, so ~90% of calls are untouched and the worst
# case drops from 1_546 to 211 tokens for that line.
#
# Capped rather than dropped: at the median of 6 areas this field is real topical
# signal, and dropping it outright pushed on-topic queries *below* the collection's own
# canary noise floor, making `weak_match` fire on valid searches. German is uncapped —
# its taxonomy is curated and short by construction.
#
# This governs the embedded text only. `funding_area` is untouched in the payload, so
# it is still returned by the API and still filterable through `funding_area_keys`.
HEADER_LIST_CAPS: Dict[str, Dict[str, int]] = {
    "eu": {"funding_area": 20},
}


def _header_value(value: object, cap: Optional[int] = None) -> str | None:
    """Render one header field, or None when it holds nothing worth embedding.

    Lists are joined; the placeholder and blanks are dropped. Applied per element
    for lists too, because a taxonomy list can contain the "Unknown" bucket.

    `cap`, when given, keeps only the first `cap` elements. It is applied *after*
    the placeholder filter so a dropped element never consumes a slot.
    """
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        parts = [
            text
            for text in (str(item).strip() for item in value if item is not None)
            if text and text != PLACEHOLDER_VALUE
        ]
        if cap is not None:
            parts = parts[:cap]
        return ", ".join(parts) or None
    text = str(value).strip()
    if not text or text == PLACEHOLDER_VALUE:
        return None
    return text


def build_context_header(metadata: dict, collection_type: Optional[str] = None) -> str:
    """Build the contextual header prepended to every chunk of a project.

    Args:
        metadata (dict): The project's row, as written to the Qdrant payload.
        collection_type (str, optional): ``"german"`` or ``"eu"``. Selects the
            per-collection list caps in `HEADER_LIST_CAPS`; ``None`` caps nothing,
            which is the German field set.

    Returns:
        str: Header text ending in a blank line, or an empty string when the
            project states none of the header fields.
    """
    caps = HEADER_LIST_CAPS.get(collection_type or "", {})
    lines = []
    for field, label in CONTEXT_HEADER_FIELDS:
        rendered = _header_value(metadata.get(field), caps.get(field))
        if rendered is not None:
            lines.append(f"{label}: {rendered}")
    if not lines:
        return ""
    return "\n".join(lines) + "\n\n"


def _canonical_json(value: Any) -> str:
    """Serialise a value so equal content always produces equal bytes.

    Same convention as `TaxonomyContractBuilder.build_taxonomy_artifact`. ``default=str``
    covers the EU rows, whose ``date_1``/``date_2`` are `datetime` objects rather than
    strings.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    """SHA-256 hex digest of the canonical serialisation of `value`."""
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def compute_content_hash(
        metadata: dict,
        description: str,
        collection_type: Optional[str] = None,
) -> str:
    """Fingerprint the text that actually gets embedded for a project.

    Covers the contextual header and the chunked body, so it moves when the source
    text changes *and* when we change what the header is made of — a new field in
    `CONTEXT_HEADER_FIELDS`, an entry in `HEADER_FIELD_EXCLUSIONS`, a vocabulary
    entry, a parser mapping. That is the case a marker taken from upstream (such as
    a `last_updated` column) cannot see.

    Because the header is per collection, the same row fingerprints differently in
    the German and EU collections. That is what makes an exclusion change re-embed
    only the collection it applies to.

    It deliberately does **not** cover the embedding recipe (model name, chunk size,
    overlap, `ADAPTIVE_CHUNK_THRESHOLD`). Changing one of those invalidates every
    vector in the collection and needs a deliberate full rebuild, not an implicit one.

    Args:
        metadata (dict): The project's parquet row.
        description (str): The text passed to `EmbeddingService.chunk_text`.
        collection_type (str, optional): ``"german"`` or ``"eu"``; selects the header
            field set, as in `build_context_header`.

    Returns:
        str: Hex SHA-256 digest.
    """
    return _digest(
        {
            "header": build_context_header(metadata, collection_type),
            "description": description or "",
        }
    )


def compute_payload_hash(metadata: dict) -> str:
    """Fingerprint the fields the search API returns for a project.

    Absent keys are normalised the way `_aggregate_results` normalises them — missing
    scalar to ``""``, missing list to ``[]``. Without that, the German and EU
    collections could never produce comparable hashes: EU carries no `status_note`,
    `deadlines` or `keywords_extracted` and only one `*_keys` field, while German
    carries no `date_1`/`date_2`.

    Args:
        metadata (dict): The project's parquet row.

    Returns:
        str: Hex SHA-256 digest.
    """
    normalized: Dict[str, Any] = {}
    for field in PAYLOAD_DISPLAY_FIELDS:
        value = metadata.get(field)
        if field in PAYLOAD_LIST_FIELDS:
            if value is None:
                normalized[field] = []
            elif isinstance(value, (list, tuple)):
                normalized[field] = list(value)
            else:
                normalized[field] = [value]
        else:
            normalized[field] = "" if value is None else value
    return _digest(normalized)


def build_project_payload(
        metadata: dict,
        project_id: str,
        description: str,
        collection_type: Optional[str] = None,
) -> dict:
    """Build the project-level Qdrant payload, hashes included.

    Shared by the insert path and the payload-refresh path so the two cannot write
    different payloads for the same row. ``chunk_index`` is not set here: it is the
    one payload key that differs between the chunks of a project, so the caller adds
    it — and leaving it out is what lets a payload refresh use `set_payload`, which
    merges and therefore preserves each chunk's own index.

    Every displayed field is written explicitly, filled with its normalised empty
    value when the row does not state it. `set_payload` merges rather than replaces,
    so a key simply left out would keep whatever it held when the project was last
    embedded — a `status_note` that upstream has since withdrawn would stay on the
    result card forever. Writing the empty value clears it instead. This uses the
    same normalisation as `compute_payload_hash`, so the fill never moves a hash and
    never triggers a re-index of its own.

    Args:
        metadata (dict): The project's parquet row.
        project_id (str): Project UUID.
        description (str): The text being embedded, for the content hash.
        collection_type (str, optional): ``"german"`` or ``"eu"``; selects the header
            field set behind the content hash, as in `build_context_header`.

    Returns:
        dict: Payload without ``chunk_index``.
    """
    payload = {k: v for k, v in metadata.items() if k not in PAYLOAD_EXCLUDE_FIELDS}
    for field in PAYLOAD_DISPLAY_FIELDS:
        if payload.get(field) is None:
            payload[field] = [] if field in PAYLOAD_LIST_FIELDS else ""
    payload["project_uuid"] = project_id
    payload["content_hash"] = compute_content_hash(metadata, description, collection_type)
    payload["payload_hash"] = compute_payload_hash(metadata)
    return payload


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
    raise RuntimeError(f"Failed to load {file_path} after {retries} retries")


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
        if overlap_tokens >= max_tokens:
            raise ValueError(
                f"overlap_tokens ({overlap_tokens}) must be less than "
                f"max_tokens ({max_tokens}) to prevent infinite chunking loops"
            )

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
            # %r, not %s: every httpx timeout stringifies to "" (httpcore raises them
            # from a bare TimeoutError), so %s logged a bare colon and an OOM-killed
            # Ollama was indistinguishable from a connection refusal.
            logger.error("Batch embedding request failed: %r", e)
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
        http_client (httpx.AsyncClient, optional): Shared HTTP client reused across
            embedding requests. When ``None`` a temporary client is created per run.
        collection_type (str, optional): ``"german"`` or ``"eu"``. Keys the
            first-seen record that saved-search alerts use to recognise new
            programmes; when ``None`` no first-seen stamping happens.

    Example:
        pipeline = Pipeline(qdrant_manager, embedding_service, "data/german_parquet_data_uuid.parquet")
        await pipeline.manage_embeddings()
    """

    def __init__(
            self,
            qdrant: QdrantManager,
            embed_service: EmbeddingService,
            file_path: str,
            http_client: Optional[httpx.AsyncClient] = None,
            collection_type: Optional[str] = None,
    ):
        """Store references to the Qdrant manager, embedding service, and data file path.

        Args:
            qdrant (QdrantManager): Qdrant collection manager for insert/delete/scroll.
            embed_service (EmbeddingService): Service that chunks text and fetches embeddings.
            file_path (str): Path to the UUID Parquet file produced by ``CommonDataPipeline``.
            http_client (httpx.AsyncClient, optional): Shared HTTP client to reuse for
                embedding requests. When ``None`` a temporary client is created per run.
            collection_type (str, optional): ``"german"`` or ``"eu"``; see the class docs.
        """
        self.qdrant = qdrant
        self.embed_service = embed_service
        self.file_path = file_path
        self.http_client = http_client
        self.collection_type = collection_type

    async def manage_embeddings(self) -> None:
        """Run the full incremental embedding pipeline.

        Sorts every project into one of four buckets and acts on each:

        1. **delete** — indexed but no longer active.
        2. **insert** — active but not yet indexed.
        3. **re-embed** — indexed, but the embedded text changed.
        4. **payload refresh** — indexed with the same text, but a displayed field
           changed. Handled with `set_payload`, so it costs no embedding call.

        A project whose stored hashes are missing lands in bucket 3, which is what
        makes the first run after this feature ships a full re-index.
        """
        df = self._load_and_normalize_data()
        indexed = self._fetch_indexed_state()

        ids_to_delete = set(self._delete_removed_projects(df, set(indexed)))
        for project_id in ids_to_delete:
            indexed.pop(project_id, None)

        new_ids = self._record_first_seen(df, set(indexed))

        rows_to_embed, stale_ids, payload_updates = self._plan_index_updates(df, indexed)

        logger.info(
            "Embedding plan: %s deleted, %s to embed (%s of them re-embeds), "
            "%s payload-only refreshes",
            len(ids_to_delete), rows_to_embed.height, len(stale_ids),
            len(payload_updates),
        )

        if stale_ids:
            # Delete before re-inserting. Chunk point IDs are uuid5(project, "chunk_i"),
            # so a project that now produces fewer chunks would otherwise leave the
            # surplus behind — still carrying the project_uuid, so still returned by
            # search and folded into the project's aggregated score.
            self.qdrant.delete_projects(stale_ids)

        if not rows_to_embed.is_empty():
            await self._embed_and_insert_rows(rows_to_embed)

        for project_id, payload in payload_updates:
            self.qdrant.set_project_payload(project_id, payload)

        if new_ids:
            self._mark_duplicates(new_ids)

    def _record_first_seen(self, df: pl.DataFrame, indexed_ids: set[str]) -> list[str]:
        """Stamp every active programme that has no first-seen row yet.

        A programme not yet in Qdrant is a genuine new arrival and is stamped with
        the current time. One that is already indexed but unstamped predates
        first-seen tracking, so it gets the legacy epoch and can never count as
        new — that is what stops the first run after rollout from replaying the
        whole index as alerts. Existing rows are never touched, so a programme that
        is deleted and later re-inserted keeps its original time.

        Runs before the embedding step so the stamp reflects when the programme
        appeared upstream, not when embedding happened to finish. Database errors
        are logged inside `first_seen` and never block embedding.

        Args:
            df (pl.DataFrame): Full funding DataFrame, including deleted rows.
            indexed_ids (set[str]): Project UUIDs currently indexed in Qdrant, with
                the ones just deleted already removed.

        Returns:
            list[str]: The programmes stamped as genuinely new in this run.

        A burst of "new" programmes in a collection that was already tracked is
        almost always upstream ids changing (a re-keying), not a wave of real
        arrivals. Announcing it would send every alert user a copy of the index, so
        such a burst is stamped with the legacy epoch instead and logged as an error.
        """
        if not self.collection_type:
            return []
        active_ids = df.filter(pl.col("deleted") == False)["uuid"].to_list()
        stamped = fetch_known_ids(self.collection_type, active_ids)
        missing = [pid for pid in active_ids if pid not in stamped]
        ids_now = [pid for pid in missing if pid not in indexed_ids]
        ids_legacy = [pid for pid in missing if pid in indexed_ids]

        burst_limit = max(FIRST_SEEN_BURST_MIN, FIRST_SEEN_BURST_RATIO * len(active_ids))
        if stamped and len(ids_now) > burst_limit:
            logger.error(
                "%s: %d programmes appeared at once (limit %d of %d active). This looks "
                "like upstream ids changing, not new programmes; stamping them as "
                "legacy so they do not trigger alerts.",
                self.collection_type, len(ids_now), int(burst_limit), len(active_ids),
            )
            ids_legacy += ids_now
            ids_now = []

        record_first_seen(self.collection_type, ids_now=ids_now, ids_legacy=ids_legacy)
        return ids_now

    def _mark_duplicates(self, new_ids: list[str]) -> None:
        """Mark new programmes that are near-copies of an existing one.

        The Förderdatenbank carries many near-identical programmes (state variants,
        a successor re-published under a new id). A new programme whose first chunk
        is at least ``DUPLICATE_COSINE`` similar to an older programme is recorded
        as its duplicate and does not alert as new. Programmes that are new in the
        same run are not compared with each other.

        Failures are logged and skipped: the cost is at most a duplicate alert.

        The Qdrant lookups stay per programme, but the marks are collected and
        written in one statement at the end — a connection per duplicate made the
        first run after a re-index open hundreds of them.
        """
        pairs: list[tuple[str, str]] = []
        for project_id in new_ids:
            try:
                vector = self.qdrant.project_vector(project_id)
                if vector is None:
                    continue
                nearest = self.qdrant.best_chunk_per_project(
                    vector, exclude=new_ids, limit=1, with_payload=["project_uuid"]
                )
            except Exception:
                logger.exception("Duplicate check failed for %s", project_id)
                continue
            if not nearest or nearest[0].score < DUPLICATE_COSINE:
                continue
            original = (nearest[0].payload or {}).get("project_uuid")
            if original:
                logger.info(
                    "%s: %s is a near-duplicate of %s (cosine %.3f); it will not alert",
                    self.collection_type, project_id, original, nearest[0].score,
                )
                pairs.append((project_id, original))

        mark_duplicates(self.collection_type, pairs)

    def _plan_index_updates(
            self,
            df: pl.DataFrame,
            indexed: dict[str, dict],
    ) -> tuple[pl.DataFrame, list[str], list[tuple[str, dict]]]:
        """Sort the active rows into the embed, re-embed and payload-refresh buckets.

        Pure and synchronous, so the classification can be tested without Qdrant or
        Ollama.

        Args:
            df (pl.DataFrame): Full funding DataFrame, including deleted rows.
            indexed (dict[str, dict]): Per-project stored hashes, from
                `_fetch_indexed_state`, with the deleted projects already removed.

        Returns:
            tuple: ``(rows_to_embed, stale_ids, payload_updates)`` — the rows needing
                an embedding pass, the subset of those already indexed (which must be
                deleted first), and ``(project_uuid, payload)`` pairs whose payload can
                be refreshed in place.
        """
        active_rows = df.filter(pl.col("deleted") == False)

        uuids_to_embed: list[str] = []
        stale_ids: list[str] = []
        payload_updates: list[tuple[str, dict]] = []

        for row in active_rows.iter_rows(named=True):
            project_id = row["uuid"]
            stored = indexed.get(project_id)
            description = row.get("description") or ""

            if stored is None:
                uuids_to_embed.append(project_id)
                continue

            if stored.get("content_hash") != compute_content_hash(
                row, description, self.collection_type
            ):
                uuids_to_embed.append(project_id)
                stale_ids.append(project_id)
                continue

            if stored.get("payload_hash") != compute_payload_hash(row):
                payload_updates.append((
                    project_id,
                    build_project_payload(
                        row, project_id, description, self.collection_type
                    ),
                ))

        rows_to_embed = active_rows.filter(pl.col("uuid").is_in(uuids_to_embed))
        return rows_to_embed, stale_ids, payload_updates

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
            "Deleting %d stale projects from Qdrant", len(ids_to_delete)
        )
        self.qdrant.delete_projects(ids_to_delete)

        return ids_to_delete

    async def _embed_and_insert_rows(
            self,
            new_rows: pl.DataFrame,
            client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        """Embed and upsert all rows in ``new_rows`` into Qdrant with bounded concurrency.

        Builds one async task per project and runs them concurrently, gated by
        an ``asyncio.Semaphore`` of size ``EMBEDDING_CONCURRENCY`` to avoid
        overwhelming the Ollama API.

        When a shared ``client`` (or ``self.http_client``) is provided it is
        reused without creating a new connection pool.  Falls back to a
        temporary ``httpx.AsyncClient`` when neither is available.

        Args:
            new_rows (pl.DataFrame): Active, not-yet-indexed rows to process.
            client (httpx.AsyncClient, optional): HTTP client override; takes
                precedence over ``self.http_client``.
        """
        descriptions = new_rows["description"].cast(pl.Utf8).to_list()
        metadata_list = new_rows.to_dicts()
        ids = new_rows["uuid"].to_list()

        semaphore = asyncio.Semaphore(EMBEDDING_CONCURRENCY)

        async def _bounded(http: httpx.AsyncClient, desc: str, meta: dict, pid: str) -> None:
            async with semaphore:
                await self._process_single_project(http, desc, meta, pid)

        effective_client = client or self.http_client

        if effective_client is not None:
            await asyncio.gather(*(
                _bounded(effective_client, desc, meta, pid)
                for desc, meta, pid in zip(descriptions, metadata_list, ids)
            ))
        else:
            async with httpx.AsyncClient(
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
                timeout=OLLAMA_EMBED_TIMEOUT_SECONDS,
            ) as tmp_client:
                await asyncio.gather(*(
                    _bounded(tmp_client, desc, meta, pid)
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

        Each chunk gets a unique point ID (``{project_id}_chunk_{i}``) and the
        contextual header built by `build_context_header`. The enriched chunk text
        is passed separately for sparse vector construction.

        Args:
            client (httpx.AsyncClient): Shared async HTTP client for Ollama requests.
            description (str): Full project description text to embed.
            metadata (dict): Payload dict stored alongside each point in Qdrant.
            project_id (str): UUID used as the base for Qdrant point IDs.
        """
        text_chunks = self.embed_service.chunk_text(description)

        header = build_context_header(metadata, self.collection_type)

        enriched_chunks = [f"{header}{chunk}" for chunk in text_chunks]

        embeddings_batch = await self.embed_service.fetch_embeddings_batch(client, enriched_chunks)
        indexed_embeddings = [
            (i, emb) for i, emb in enumerate(embeddings_batch) if emb is not None
        ]

        if not indexed_embeddings:
            logger.warning("No embeddings generated for project %s", project_id)
            return

        project_ns = uuid.UUID(project_id)
        chunk_ids = [str(uuid.uuid5(project_ns, f"chunk_{i}")) for i, _ in indexed_embeddings]
        embeddings = [emb for _, emb in indexed_embeddings]
        chunk_texts = [enriched_chunks[i] for i, _ in indexed_embeddings]

        project_payload = build_project_payload(
            metadata, project_id, description, self.collection_type
        )
        chunk_metadata = []
        for i, _ in indexed_embeddings:
            meta = dict(project_payload)
            meta["chunk_index"] = i
            chunk_metadata.append(meta)

        self.qdrant.insert_projects(
            embeddings=embeddings,
            metadata_list=chunk_metadata,
            ids=chunk_ids,
            chunk_texts=chunk_texts,
        )

        logger.info(
            "Inserted %d chunks for project %s",
            len(indexed_embeddings), project_id,
        )

    def _fetch_indexed_state(self) -> dict[str, dict]:
        """Scroll the collection and return each indexed project's stored hashes.

        Reads ``project_uuid`` plus the two change markers from each point. For legacy
        points lacking ``project_uuid`` (pre-migration), the point ID is used as a
        fallback. Every chunk of a project carries the same hashes, so the first
        chunk seen wins.

        A project indexed before this feature shipped has no hashes; it yields
        ``None`` for both, which `_plan_index_updates` treats as changed.

        Returns:
            dict[str, dict]: ``{project_uuid: {"content_hash": …, "payload_hash": …}}``.

        Raises:
            Exception: Propagates any Qdrant scroll error so callers can abort
                the embedding run rather than silently treating the collection
                as empty.
        """
        state: dict[str, dict] = {}
        offset = None
        while True:
            points, offset = self.qdrant.client.scroll(
                collection_name=self.qdrant.collection_name,
                limit=256,
                with_payload=["project_uuid", "content_hash", "payload_hash"],
                with_vectors=False,
                offset=offset,
            )
            for p in points:
                payload = p.payload or {}
                project_id = payload.get("project_uuid") or str(p.id)
                if project_id in state:
                    continue
                state[project_id] = {
                    "content_hash": payload.get("content_hash"),
                    "payload_hash": payload.get("payload_hash"),
                }
            if offset is None:
                break
        logger.info("Fetched %d existing project IDs from Qdrant", len(state))
        return state
