# `streamlit.utils.utils`

Provides shared helper functions for the Streamlit frontend, including API calls, result rendering, and error handling.

## Internal Helpers

### `_api_headers()`

Builds HTTP headers for internal FastAPI requests. Includes the `X-Internal-Token` header when the `INTERNAL_API_TOKEN` environment variable is set, allowing the FastAPI `InternalTokenMiddleware` to authenticate the caller.

## General Helpers

### `safe_join(value, sep=", ", default="N/A")`

Joins list-like values into a display string and falls back to a default label for empty or None values.

## Taxonomy and Search

### `fetch_german_taxonomy(fastapi_url, timeout=30)`

Fetches `GET /v1/vocab/german` and returns a safe dictionary structure containing taxonomy columns.
Result is cached by Streamlit for 300 seconds to avoid redundant API calls on every sidebar re-render.

### `search_projects(fastapi_url, model, query, search_limit, endpoint, semantic_weight=0.7, filters=None, timeout=30)`

Sends a search request to FastAPI and returns the `matches` list from the JSON response.

- `semantic_weight`: hybrid search weight forwarded to the backend (0=keyword, 1=semantic).
- `filters`: optional taxonomy filters and `drop_na` flag forwarded to the backend for server-side filtering.

## Rendering Helpers

### `render_german_project_result(result)`

Renders one German funding result card with title, short/full descriptions, on-website and last-updated dates, funding type, location, area, eligible applicants, and score.

### `_parse_datetime(value)`

Parses a datetime-like value into a Python `datetime` object when possible.

### `render_eu_project_result(result)`

Renders one EU funding result card with description, opening date, deadline, and score.

### `_friendly_search_error(error)`

Maps a search exception to a user-facing error message suitable for `st.error(...)`.
