# `streamlit.utils.utils`

Provides shared helper functions for the Streamlit frontend, including API calls, taxonomy-aware filtering, result aggregation, and result rendering.

## General Helpers

### `safe_join(value, sep=", ", default="N/A")`

Joins list-like values into a display string and falls back to a default label for empty values.

### `normalize_list(value)`

Converts scalars and iterable values into a list of strings.

### `read_extracted_filter_options(file_path, retries=10, delay=1)`

Reads values from a text file with retry/backoff. This helper remains available for local file use-cases.

## Taxonomy and Search

### `fetch_german_taxonomy(fastapi_url, timeout=30)`

Fetches `GET /v1/vocab/german` and returns a safe dictionary structure containing taxonomy columns.

### `search_projects(fastapi_url, model, query, search_limit, endpoint, filters=None, timeout=30)`

Sends a search request to FastAPI and returns the `matches` list from the JSON response.

### `apply_filters(matches, filters)`

Applies key-based filters on German results using `*_keys` fields:

- `funding_location_keys`
- `funding_type_keys`
- `eligible_applicants_keys`
- `funding_area_keys`

Also supports the `drop_na` toggle to hide entries where both short and full descriptions are `"N/A"`.

### `aggregate_chunks(matches)`

Merges chunk-level matches by project ID and keeps the maximum `matching_score`.

## Rendering Helpers

### `render_german_project_result(result)`

Renders one German funding result card with title, descriptions, dates, category metadata, and score.

### `_parse_datetime(value)`

Parses a datetime-like value into a Python `datetime` object when possible.

### `render_eu_project_result(result)`

Renders one EU funding result card with description, opening date, deadline, and score.
