# `streamlit.utils.utils`

Provides shared helper functions for the Streamlit frontend, including API calls, local filter loading, result aggregation, filtering, and result rendering.

## General Helpers

### `safe_join(value, sep=", ", default="N/A")`

Joins list-like values into a display string and falls back to a default label for empty values.

### `normalize_list(value)`

Converts scalars and iterable values into a list of strings.

### `read_extracted_filter_options(file_path, retries=10, delay=1)`

Reads filter values from a text file with retry and exponential backoff when the file is temporarily unavailable.

## Search and Filtering

### `apply_filters(matches, filters)`

Applies frontend filters to German funding results.

Supported filters:

- `locations`
- `funding_type`
- `eligible`
- `funding_area`
- `drop_na`

### `aggregate_chunks(matches)`

Merges multiple chunk-level results belonging to the same project and keeps the best `matching_score`.

### `search_projects(fastapi_url, model, query, search_limit, semantic_weight, endpoint, timeout=30)`

Sends a search request to the FastAPI backend and returns the `matches` list from the JSON response.

## Rendering Helpers

### `render_german_project_result(result)`

Renders one German funding result card with title, descriptions, dates, filter metadata, and score.

### `_parse_datetime(value)`

Parses a datetime-like value into a Python `datetime` object when possible.

### `render_eu_project_result(result)`

Renders one EU funding result card with description, opening date, deadline, and score.
