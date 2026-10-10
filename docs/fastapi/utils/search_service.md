# `fastapi.utils.search_service`

The search path — embed, search, aggregate, filter — plus the alert scoring built on
the same primitives. Split out of `main.py`, which had grown to hold the HTTP layer,
the scheduler and this logic at once.

Nothing here touches FastAPI's `app` or the module-level Qdrant managers: every entry
point takes the collection to work on as an argument, which is what lets the same code
serve the two search routes and the nightly alert run. `main._alert_score_fn` is the
one piece left behind, because it is what binds these functions to the module-level
`german_qdrant_manager` / `eu_qdrant_manager`.

`HTTPException` is imported deliberately: `embed_query` maps an unreachable Ollama to a
503, which is genuinely an HTTP-layer decision, and raising a domain error here to
translate in each route would buy nothing but indirection.

---

### `_normalize_list_field(value: Any) -> list[Any]`

Wrap a scalar in a list; return lists unchanged; return `[]` for `None`.

**Parameters:**

- `value` (`Any`): Scalar, list, or `None`.

**Returns:** `list[Any]`

---

### `_normalize_filter_keys(filters: SearchFilters) -> dict[str, set[str]]`

Convert a `SearchFilters` object to normalised taxonomy key sets.

**Parameters:**

- `filters` (`SearchFilters`): Filter model from the request body.

**Returns:** `dict[str, set[str]]` — mapping from field name to its set of normalised taxonomy keys. Fields with no selected values are omitted.

---

### `_result_matches_filters(result: dict[str, Any], filter_keys: dict[str, set[str]]) -> bool`

Return `True` if a result satisfies all active taxonomy filters (AND across fields, OR within each field).

**Parameters:**

- `result` (`dict[str, Any]`): Aggregated result dict from `aggregate_results`.
- `filter_keys` (`dict[str, set[str]]`): Normalised key sets from `_normalize_filter_keys`.

**Returns:** `bool`

---

### `aggregate_results(results: list[Any]) -> list[dict[str, Any]]`

Deduplicate Qdrant chunk-level results by project using TopK-Avg scoring.

Groups by `project_uuid` from the point payload (falls back to the raw point ID for legacy points). Uses `heapq.nlargest(TOPK_SCORES, ...)` per project. The final score is the average of the top-K chunk scores.

**Parameters:**

- `results` (`list[Any]`): Raw `ScoredPoint` list from `QdrantManager.search`.

**Returns:** `list[dict[str, Any]]` — deduplicated result dicts each containing a `score` field.

The field is called `score` and deliberately carries no scale in its name: it is the TopK-Avg of whatever the caller put in. Interactive search passes fused Convex-Combination scores and derives `relative_score`; the alert path passes raw dense cosines and derives `dense_score`. Those two are not comparable, which is why neither name is reused here.

---

### `await_ollama_model(client: httpx.AsyncClient) -> None`

Block until the Ollama embedding model is ready to serve requests.

Sends a test embed request every `OLLAMA_MODEL_READY_INTERVAL` seconds, retrying on 404 (model still pulling) and connection errors.

**Parameters:**

- `client` (`httpx.AsyncClient`): Shared HTTP client from `app.state`.

**Returns:** `None`

**Raises:** `TimeoutError` — if the model is not ready within `OLLAMA_MODEL_READY_TIMEOUT` seconds.

---

### `embed_query(query: str, model: str, client: httpx.AsyncClient) -> list[float]`

Fetch a dense embedding vector for a search query from the Ollama API.

Retries once on `httpx.ConnectError`. Maps all Ollama failures to HTTP 503.

**Parameters:**

- `query` (`str`): User's search text.
- `model` (`str`): Ollama model name, e.g. `"bge-m3"`.
- `client` (`httpx.AsyncClient`): Shared HTTP client from `app.state`.

**Returns:** `list[float]` — dense embedding vector.

**Raises:** `HTTPException(503)` — when Ollama is unavailable or returns a non-2xx response.

---

### `apply_result_filters(matches: list[dict[str, Any]], filters: SearchFilters) -> list[dict[str, Any]]`

Keep the matches that satisfy the taxonomy filters and the drop-N/A option. Shared by interactive search and the alert job, so a saved search's filters mean the same thing in both.

---

### `search_collection(body: SearchRequest, qdrant_manager: QdrantManager, client: httpx.AsyncClient) -> dict[str, Any]`

Core search handler: embed query → hybrid search → aggregate chunks → normalise scores → apply filters → sort.

**Parameters:**

- `body` (`SearchRequest`): Validated search request.
- `qdrant_manager` (`QdrantManager`): Collection to search against.
- `client` (`httpx.AsyncClient`): Shared HTTP client for embedding calls.

**Returns:** `dict[str, Any]` — `{"matches": [<result_dict>, ...], "weak_match": bool}` ready for JSON serialisation.

Filters are applied **before** normalising, and the scores that survive are divided by the best of them. The other order divides by a programme the filters then remove, so the visible list has no `1.0` row and is scaled against something the user never sees. The accepted cost is that a displayed score moves when a filter is toggled.

---

### `collection_noise_floor(qdrant_manager: QdrantManager, collection_type: str, client: httpx.AsyncClient) -> float`

The collection's alert noise floor: the best cosine any `match_levels.CANARIES` query reaches there, plus `ALERT_NOISE_MARGIN`. Embeds the canaries once per collection and caches the result in `_NOISE_FLOORS`, which `invalidate_noise_floor` clears after that collection's embedding run. See [Saved-Search Alerts](alerts.md).

---

### `invalidate_noise_floor(qdrant_manager: QdrantManager) -> None`

Forget a collection's cached noise floor. Called after each embedding run, because new programmes can change what the canaries reach. `main.py` re-measures it immediately afterwards (`_rewarm_noise_floor`) so the cost lands on the pipeline rather than on the first search.

---

### `is_weak_match(qdrant_manager, collection_type, query_vector, client) -> bool`

Whether nothing in the collection is a genuinely relevant match for the query — the absolute check that `relative_score` cannot provide, since the top match always scores `1.0` and *something* is always ranked first.

Compares the collection's canary noise floor against the best raw cosine the query reaches anywhere in it, via `best_chunk_per_project`. It must be the dense best-chunk cosine and **not** the fused search score: the fused score blends two min-max-normalised branches and is not a cosine at all, so it is not on the floor's scale.

Taken deliberately **pre-filter**, so the flag means "this query is off-topic for this collection", not "your filters were too narrow" — different problems wanting different wording in the UI.

Best-effort by design. A cold `_NOISE_FLOORS` costs one embedding call per canary, so an unmeasured floor returns `False` rather than making a user wait for it. Any failure also returns `False`: a missing hint beats a failed search.

**Returns:** `bool` — `True` only when the floor is known and the query falls below it.

---

### `alert_scores(qdrant_manager, query_vector, candidate_ids, filters) -> tuple[list[dict], list[float]]`

Blocking; run in a thread. Two grouped Qdrant queries:

1. exact best-chunk scores of the candidate programmes, aggregated and filtered like a normal search (`dense_score` is the best-chunk cosine — a raw cosine, never the relative score interactive search returns);
2. the top `RANK_DEPTH` **existing** programmes with the candidates excluded, so new programmes are ranked against the existing ones rather than against each other.

---
