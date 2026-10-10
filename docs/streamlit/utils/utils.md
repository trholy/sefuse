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
- `filters` (`dict[str, Any] | None`, default `None`): Optional taxonomy filters forwarded to the backend.
- `timeout` (`int`, default `30`): HTTP request timeout in seconds.

**Returns:** `list[dict]` — list of matching project dicts from the `matches` key of the JSON response.

**Raises:** `requests.HTTPError` — on non-2xx responses.

---

### `render_german_project_result(result: dict) -> None`

Render a German federal funding project as a Streamlit card.

Displays the title hyperlinked to `project_website`, then every field in `GERMAN_RESULT_FIELDS`, then the matching score as a percentage.

No line is ever omitted: fields the source does not state render as `N/A` — see `display_value` and `safe_join`.

**Parameters:**

- `result` (`dict`): Project dict as returned by `search_projects`.

**Returns:** `None`

---

### `GERMAN_RESULT_FIELDS`

The German result card, in display order, as `(result key, label, is_list)` triples:

| Field | Label | List |
|---|---|---|
| `project_short_description` | Short description | |
| `project_full_description` | Full description | |
| `funding_location` | Target area | ✓ |
| `funding_type` | Type of funding | ✓ |
| `eligible_applicants` | Eligible applicants | ✓ |
| `funding_area` | Funding area | ✓ |
| `status_note` | Status | |
| `deadlines` | Deadlines | |
| `keywords_extracted` | Keywords | ✓ |
| `contact_info_institution` | Contact | |

Every field is always rendered. A programme that does not state one shows `N/A` rather than dropping the line, so the card has the same shape for every result and a reader can tell "not stated" from "you scrolled past it".

The German card shows no dates: the pipeline no longer carries the source's history columns.

---

### `display_value(value: Any) -> str`

Render a scalar result field, falling back to `"N/A"`.

Covers the three ways a field can be absent by the time it reaches the page: the data pipeline filled it with the `"N/A"` placeholder, the API defaulted it to an empty string because the collection has no such field, or the key is missing from the result dict entirely. List fields use `safe_join`, which has the same fallback.

**Parameters:**

- `value` (`Any`): Raw field value from a result dict.

**Returns:** `str` — the stripped value, or `"N/A"`.

---

### `_parse_datetime(value: Any) -> datetime | None`

Parse a datetime-like value into a `datetime` object, returning `None` on failure.

Handles ISO-8601 strings (normalises `Z` suffix to `+00:00`), existing `datetime` instances, and `None`. Used only by the EU renderer — the German card shows no dates.

**Parameters:**

- `value` (`Any`): ISO-8601 string, `datetime` instance, or `None`.

**Returns:** `datetime | None` — parsed datetime, or `None` when the value is unparseable.

---

### `DATE_DISPLAY_FORMAT`

`"%d %b %Y, %H:%M"` — the one date format the UI uses. Day-month-year with an abbreviated month and a 24-hour clock reads unambiguously to both German and English users, which a purely numeric format does not.

---

### `format_timestamp(value: datetime) -> str`

Format a known-present `datetime` per `DATE_DISPLAY_FORMAT`.

For callers holding a real timestamp from the database with nothing to fall back to — the watchlist's "Added" caption, and the Saved Searches page's created/last-run captions. Use `_display_date` instead where the value may be absent or a string, since that one falls back to `"N/A"`.

**Parameters:**

- `value` (`datetime`): The timestamp to render.

**Returns:** `str` — the formatted timestamp.

---

### `render_eu_project_result(result: dict) -> None`

Render an EU funding call as a Streamlit card.

Displays: title (hyperlinked to `project_website`), a truncated headline, a collapsed "More details" expander holding the full topic description plus the planned opening date (`date_1`) and deadline (`date_2`), and the matching score as a percentage. Every line inside the expander is always rendered, falling back to `"N/A"`.

The headline is `topic_destination` — the aims of the work programme destination the topic sits under. The EU portal states it on Horizon topics only (roughly one open call in eight), so the card falls back to `project_full_description` when it is absent rather than leaving most results blank, and truncates whichever it used at `EU_CARD_DESCRIPTION_CHARS` (400 characters). The expander always holds the untruncated topic description.

**Parameters:**

- `result` (`dict`): Project dict as returned by `search_projects`.

**Returns:** `None`

---

### `friendly_search_error(error: Exception) -> str`

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
