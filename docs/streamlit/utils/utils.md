# `streamlit.utils.utils`

Shared helper functions for the Streamlit frontend: API communication, result rendering, and error handling.

---

### `_api_headers() -> dict[str, str]`

Build HTTP headers for internal FastAPI requests.

Includes the `X-Internal-Token` header when the `INTERNAL_API_TOKEN` environment variable is set, allowing the FastAPI `InternalTokenMiddleware` to authenticate the caller.

**Returns:** `dict[str, str]` — header dict (empty if no token is configured).

---

### `safe_join(value: list[Any] | None, sep: str = ", ", default: str = "N/A") -> str`

Join a list to a display string, returning a default for empty or `None` input.

**Parameters:**

- `value` (`list[Any] | None`): List of values to join, or `None`.
- `sep` (`str`, default `", "`): Separator placed between items.
- `default` (`str`, default `"N/A"`): Returned when `value` is `None` or empty.

**Returns:** `str` — joined string or the default value.

---

### `fetch_german_taxonomy(fastapi_url: str, timeout: int = 30) -> dict[str, Any]`

Fetch the German taxonomy artifact from the FastAPI `/v1/vocab/german` endpoint.

Result is cached by Streamlit for 300 seconds (`@st.cache_data(ttl=300)`) to avoid redundant API calls on every sidebar re-render.

**Parameters:**

- `fastapi_url` (`str`): Base URL of the FastAPI service, e.g. `"http://fastapi:8000"`.
- `timeout` (`int`, default `30`): HTTP request timeout in seconds.

**Returns:** `dict[str, Any]` — taxonomy artifact with a `columns` key; returns `{"columns": {}}` on malformed responses.

**Raises:** `requests.HTTPError` — on non-2xx responses.

---

### `search_projects(fastapi_url: str, model: str, query: str, search_limit: int, endpoint: str, semantic_weight: float = 0.7, filters: dict[str, Any] | None = None, timeout: int = 30) -> list[dict]`

Send a search request to the FastAPI backend and return matched projects.

**Parameters:**

- `fastapi_url` (`str`): Base URL of the FastAPI service, e.g. `"http://fastapi:8000"`.
- `model` (`str`): Embedding model name forwarded in the request body.
- `query` (`str`): User's natural-language search text.
- `search_limit` (`int`): Maximum number of results to request.
- `endpoint` (`str`): API path, e.g. `"/v1/search/german"`.
- `semantic_weight` (`float`, default `0.7`): Hybrid search weight (0 = pure keyword, 1 = pure semantic).
- `filters` (`dict[str, Any] | None`, default `None`): Optional taxonomy filters and `drop_na` flag forwarded to the backend.
- `timeout` (`int`, default `30`): HTTP request timeout in seconds.

**Returns:** `list[dict]` — list of matching project dicts from the `matches` key of the JSON response.

**Raises:** `requests.HTTPError` — on non-2xx responses.

---

### `render_german_project_result(result: dict) -> None`

Render a German federal funding project as a Streamlit card.

Displays: title (hyperlinked to `project_website`), short description, full description, on-website date (`date_1`), last-updated date (`date_2`), funding type, target area (funding location), funding area, eligible applicants, and matching score as a percentage.

**Parameters:**

- `result` (`dict`): Project dict as returned by `search_projects`.

**Returns:** `None`

---

### `_parse_datetime(value: Any) -> datetime | None`

Parse a datetime-like value into a `datetime` object, returning `None` on failure.

Handles ISO-8601 strings (normalises `Z` suffix to `+00:00`), existing `datetime` instances, and `None`.

**Parameters:**

- `value` (`Any`): ISO-8601 string, `datetime` instance, or `None`.

**Returns:** `datetime | None` — parsed datetime, or `None` when the value is unparseable.

---

### `render_eu_project_result(result: dict) -> None`

Render an EU funding call as a Streamlit card.

Displays: title (hyperlinked to `project_website`), full description, planned opening date (`date_1`, omitted when absent), deadline (`date_2`, omitted when absent), and matching score as a percentage.

**Parameters:**

- `result` (`dict`): Project dict as returned by `search_projects`.

**Returns:** `None`

---

### `_friendly_search_error(error: Exception) -> str`

Map a search exception to a user-friendly error message for display via `st.error(...)`.

**Parameters:**

- `error` (`Exception`): Exception raised during `search_projects`.

**Returns:** `str` — human-readable message.

| Exception type | Message shown |
|---|---|
| `requests.exceptions.ConnectionError` / `ConnectionRefusedError` | Service still starting up — data download or embedding may be in progress. |
| `requests.exceptions.Timeout` | Request is taking too long — retry in a moment. |
| `requests.exceptions.HTTPError` with status 503 | Embedding service is warming up — retry in a few seconds. |
| Other `requests.exceptions.HTTPError` | Unexpected response from the search service. |
| Any other exception | Generic "something went wrong" message. |
