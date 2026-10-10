"""The search path: embed, search, aggregate, filter — plus alert scoring.

Split out of ``main.py``, which had grown to hold the HTTP layer, the scheduler and
this logic at once. Nothing here touches FastAPI's app or the module-level Qdrant
managers: every entry point takes the collection to work on as an argument, which is
what lets the same code serve the two search routes and the nightly alert run.

``HTTPException`` is imported deliberately. ``embed_query`` maps an unreachable
Ollama to a 503, and that is genuinely an HTTP-layer decision; raising a domain
error here and translating it in each route would buy nothing but indirection.
"""

from __future__ import annotations

import asyncio
import heapq
import logging
from typing import TYPE_CHECKING, Any, Dict

import httpx
from fastapi import HTTPException

from shared.taxonomy_contract import taxonomy_key_set

from .config import EMBED_MODEL, OLLAMA_EMBED_TIMEOUT_SECONDS, OLLAMA_URL
from .env import read_int
from .match_levels import CANARIES, RANK_DEPTH, noise_floor
from .search_models import SearchFilters, SearchRequest

if TYPE_CHECKING:  # QdrantManager is only ever annotated here, never constructed.
    from .qdrant_utils import QdrantManager

logger = logging.getLogger(__name__)


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


TOPK_SCORES = read_int("TOPK_SCORES", 3)
# How many top-chunk scores to average per project in aggregate_results.
# Kept as a separate name so the two concerns are explicit even though they
# share the same default value.
QDRANT_OVERFETCH_MULTIPLIER = TOPK_SCORES


def aggregate_results(results: list[Any]) -> list[dict[str, Any]]:
    """Deduplicate Qdrant results by project using TopK-Avg scoring.

    Multiple chunks from the same project may appear in search results. This
    function collapses them into one entry per project using ``project_uuid``
    from the point payload as the grouping key (falling back to the raw point
    ID for any point that lacks the field). The final score is the average of
    the top-K chunk scores per project.

    The field is called ``score`` and deliberately carries no scale in its name: it
    is the TopK-Avg of whatever the caller put in. Interactive search passes fused
    Convex-Combination scores and derives ``relative_score`` from them; the alert
    path passes raw dense cosines and derives ``dense_score``. Those two are not
    comparable, which is why neither name is reused here.

    Args:
        results (list[Any]): Raw ``ScoredPoint`` list from ``QdrantManager.search``.

    Returns:
        list[dict[str, Any]]: Deduplicated result dicts with a ``score`` field.
    """
    aggregated: Dict[str, Dict[str, Any]] = {}
    scores_by_project: Dict[str, list[float]] = {}
    for result in results:
        payload = result.payload
        if not isinstance(payload, dict):
            logger.warning("Skipping invalid payload: %s", payload)
            continue

        project_id = payload.get("project_uuid") or str(result.id)
        if project_id not in aggregated:
            aggregated[project_id] = {
                "project_id": project_id,
                "project_title": payload.get("title") or "",
                "project_short_description": payload.get("project_short_description") or "",
                "project_full_description": payload.get("project_full_description") or "",
                "topic_destination": payload.get("topic_destination") or "",
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
                "score": 0,
                "status_note": payload.get("status_note") or "",
                "deadlines": payload.get("deadlines") or "",
                "keywords_extracted": _normalize_list_field(
                    payload.get("keywords_extracted")
                ),
                "contact_info_institution": payload.get("contact_info_institution") or "",
            }
            scores_by_project[project_id] = []
        scores_by_project[project_id].append(result.score)

    for project_id, entry in aggregated.items():
        top_scores = heapq.nlargest(TOPK_SCORES, scores_by_project[project_id])
        entry["score"] = sum(top_scores) / len(top_scores)

    return list(aggregated.values())


OLLAMA_MODEL_READY_INTERVAL = read_int("OLLAMA_MODEL_READY_INTERVAL", 10)
OLLAMA_MODEL_READY_TIMEOUT = read_int("OLLAMA_MODEL_READY_TIMEOUT", 600)


async def await_ollama_model(client: httpx.AsyncClient) -> None:
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


async def embed_query(query: str, model: str, client: httpx.AsyncClient) -> list[float]:
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


async def search_collection(
    body: SearchRequest,
    qdrant_manager: QdrantManager,
    client: httpx.AsyncClient,
    collection_type: str | None = None,
) -> Dict[str, Any]:
    """Core search handler: embed query → hybrid search → aggregate → filter → normalise.

    Pipeline:
    1. Embeds ``body.messages[0].content`` via Ollama.
    2. Runs hybrid search in ``qdrant_manager`` with ``semantic_weight``.
    3. Deduplicates chunks via ``aggregate_results``.
    4. Applies taxonomy key filters and optional drop-N/A.
    5. Normalises the *surviving* scores to [0, 1] by dividing by the max.
    6. Sorts results by descending score.

    Filtering comes before normalising on purpose. The other order divides by a
    programme the filters then remove, so the visible list has no 1.0 entry and is
    scaled against something the user never sees. The cost is that the score now
    moves when a filter is toggled — which is the point: the scale refers to a row
    on screen.

    Args:
        body (SearchRequest): Validated search request.
        qdrant_manager (QdrantManager): Collection to search against.
        client (httpx.AsyncClient): Shared HTTP client for embedding calls.
        collection_type (str, optional): ``"german"`` or ``"eu"``, enabling the
            weak-match check. Omitted means no check and ``weak_match`` is False.

    Returns:
        dict: ``{"matches": [...], "weak_match": bool}`` ready for JSON
        serialisation. See :func:`is_weak_match` for what the flag means.
    """
    query = body.messages[0].content
    model = body.model
    limit = body.limit
    semantic_weight = body.semantic_weight

    query_vector = await embed_query(query, model, client)
    results, weak_match = await asyncio.gather(
        asyncio.to_thread(
            qdrant_manager.search,
            query_vector=query_vector,
            query_text=query,
            limit=limit * QDRANT_OVERFETCH_MULTIPLIER,
            semantic_weight=semantic_weight,
        ),
        is_weak_match(qdrant_manager, collection_type, query_vector, client),
    )
    aggregated = aggregate_results(results)

    # Filter first, then normalise against what is left. See the note above.
    filtered = apply_result_filters(aggregated, body.filters)
    if filtered:
        top_score = max(match["score"] for match in filtered)
        for match in filtered:
            match["relative_score"] = (
                match["score"] / top_score if top_score > 0 else 0.0
            )

    filtered.sort(key=lambda m: m["relative_score"], reverse=True)
    return {"matches": filtered[:limit], "weak_match": weak_match}


def apply_result_filters(
    matches: list[dict[str, Any]], filters: SearchFilters
) -> list[dict[str, Any]]:
    """Keep the matches that satisfy the taxonomy filters and the drop-N/A option.

    Shared by interactive search and the alert job, so a saved search's filters mean
    the same thing in both.
    """
    filter_keys = _normalize_filter_keys(filters)
    kept = []
    for match in matches:
        if filter_keys and not _result_matches_filters(match, filter_keys):
            continue
        if filters.drop_na:
            short = match.get("project_short_description", "")
            full = match.get("project_full_description", "")
            if short == "N/A" and full == "N/A":
                continue
        kept.append(match)
    return kept


# Noise floor per collection name, measured once and reused until the collection is
# re-indexed; see ``collection_noise_floor``.
_NOISE_FLOORS: dict[str, float] = {}


def invalidate_noise_floor(qdrant_manager: QdrantManager) -> None:
    """Forget a collection's noise floor, e.g. after its embedding run."""
    _NOISE_FLOORS.pop(qdrant_manager.collection_name, None)


async def collection_noise_floor(
    qdrant_manager: QdrantManager, collection_type: str, client: httpx.AsyncClient
) -> float:
    """Return the collection's noise floor: the best canary cosine plus a margin.

    Embeds the collection-language canaries and takes the best programme each one
    finds. Deterministic for a given index, so it is cached until the next
    embedding run changes the collection.
    """
    name = qdrant_manager.collection_name
    if name not in _NOISE_FLOORS:
        canary_top1 = []
        for canary in CANARIES[collection_type]:
            vector = await embed_query(canary, EMBED_MODEL, client)
            hits = await asyncio.to_thread(
                qdrant_manager.best_chunk_per_project, vector, limit=1, with_payload=False
            )
            if hits:
                canary_top1.append(hits[0].score)
        _NOISE_FLOORS[name] = noise_floor(canary_top1)
        logger.info(
            "Alert noise floor for %s: %.3f (best of %d canaries + margin)",
            name, _NOISE_FLOORS[name], len(canary_top1),
        )
    return _NOISE_FLOORS[name]


async def is_weak_match(
    qdrant_manager: QdrantManager,
    collection_type: str | None,
    query_vector: list[float],
    client: httpx.AsyncClient,
) -> bool:
    """Whether nothing in the collection is a genuinely relevant match for the query.

    The score the API returns is relative to the best hit in the result set, so its
    top entry is always 1.0 — for "cheesecake recipe" as much as for a real project
    description. Rank cannot say a match is relevant, because *something* is always
    ranked first. This is the absolute check that can, and it reuses the alert
    machinery: the collection's canary noise floor, measured once per index
    generation, versus the best raw cosine this query reaches anywhere in it.

    The comparison deliberately uses :meth:`QdrantManager.best_chunk_per_project`
    rather than the fused search score, because the fused score is a blend of two
    min-max-normalised branches and is not a cosine at all — only the dense
    best-chunk score is on the same scale as the floor.

    It is also deliberately taken *before* filters, so the flag means "this query is
    off-topic for this collection", not "your filters were too narrow". Those are
    different problems and want different wording in the UI.

    Best-effort by design. A cold ``_NOISE_FLOORS`` cache costs one embedding call
    per canary, so when the floor is not yet measured this returns False rather than
    making a user wait for it; the embedding run re-warms it (see ``main.py``).

    Returns:
        bool: True only when the floor is known and the query's best cosine in the
        collection falls below it. Any failure returns False — a missing hint is
        better than a failed search.
    """
    if collection_type is None:
        return False
    if qdrant_manager.collection_name not in _NOISE_FLOORS:
        logger.debug(
            "Noise floor for %s not measured yet; skipping the weak-match check",
            qdrant_manager.collection_name,
        )
        return False
    try:
        floor = await collection_noise_floor(qdrant_manager, collection_type, client)
        hits = await asyncio.to_thread(
            qdrant_manager.best_chunk_per_project,
            query_vector,
            limit=1,
            with_payload=False,
        )
    except Exception:
        logger.warning("Weak-match check failed; reporting no weak match", exc_info=True)
        return False
    if not hits:
        return False
    return hits[0].score < floor


def alert_scores(
    qdrant_manager: QdrantManager,
    query_vector: list[float],
    candidate_ids: list[str],
    filters: SearchFilters,
) -> tuple[list[dict[str, Any]], list[float]]:
    """Score alert candidates and rank the query against existing programmes.

    Blocking (two Qdrant queries); run it in a thread.

    Returns:
        tuple: The candidates that pass ``filters``, as result dicts whose
        ``dense_score`` is their best-chunk cosine, and the best-chunk cosines of
        the query's top existing programmes with every candidate left out, so new
        programmes are ranked against the existing ones and not against each other.
    """
    hits = qdrant_manager.best_chunk_per_project(query_vector, project_uuids=candidate_ids)
    matches = apply_result_filters(aggregate_results(hits), filters)
    for match in matches:
        # A raw cosine, not the relative score interactive search returns. The two
        # are not comparable, so they never share a field name.
        match["dense_score"] = match["score"]

    ranked = qdrant_manager.best_chunk_per_project(
        query_vector, exclude=candidate_ids, limit=RANK_DEPTH, with_payload=False
    )
    return matches, [hit.score for hit in ranked]
