# `data_processing.utils.eu_funding_fetcher`

Paginates the EU Funding & Tenders Portal search API to collect open/forthcoming English-language calls.

---

## Class `EuFundingFetcher`

Paginates the EU search API and collects open/forthcoming English-language calls. Only OPEN and FORTHCOMING calls are requested at the query level; CLOSED calls are excluded to avoid unbounded pagination. Non-English results are dropped client-side.

### `__init__(api_url: str, api_key: str, timeout_seconds: float = 30, page_delay_seconds: float = 0.2)`

**Parameters:**

- `api_url` (`str`): Base URL of the EU search endpoint.
- `api_key` (`str`): API key passed as the `apiKey` query parameter.
- `timeout_seconds` (`float`, default `30`): HTTP request timeout in seconds.
- `page_delay_seconds` (`float`, default `0.2`): Sleep between paginated requests to avoid rate-limiting.

---

### `_get_meta_value(meta: dict, key: str) -> str | None`

Extract and normalise a single string value from a metadata dict by `key`.

**Parameters:**

- `meta` (`dict`): Metadata dict from an API result.
- `key` (`str`): Key to look up in `meta`.

**Returns:** `str | None` — First non-empty string found, or `None`.

---

### `_first_string(value: object) -> str | None`

Recursively extract the first non-empty string from a scalar, dict, or list. For dicts, tries keys `code`, `id`, `value`, `label`, `text`, `name`, `content` in order.

**Parameters:**

- `value` (`object`): Any value returned by the API.

**Returns:** `str | None` — First non-empty string found, or `None`.

---

### `_normalize_meta_list(meta: dict, key: str) -> list[str]`

Return all non-empty string entries for `key` from a metadata dict.

**Parameters:**

- `meta` (`dict`): Metadata dict from an API result.
- `key` (`str`): Key to look up; value may be a scalar or list.

**Returns:** `list[str]` — Flat list of non-empty strings.

---

### `_build_portal_topic_url(identifier: str | None) -> str | None`

Construct the EU Funding & Tenders portal URL for a topic `identifier`.

**Parameters:**

- `identifier` (`str | None`): Topic identifier string from API metadata.

**Returns:** `str | None` — Full portal URL, or `None` if `identifier` is falsy.

---

### `_is_english(result_language: str | None, metadata_languages: list[str]) -> bool`

Return `True` when the result or its metadata indicates an English-language call.

**Parameters:**

- `result_language` (`str | None`): Top-level language field of the result.
- `metadata_languages` (`list[str]`): Language list from the result metadata.

**Returns:** `bool` — `True` if either source starts with `"en"` (case-insensitive).

---

### `_is_allowed_status(status_code: str | None) -> bool`

Return `True` when `status_code` is OPEN or FORTHCOMING.

**Parameters:**

- `status_code` (`str | None`): EU status code to check against `EU_ACTIVE_STATUS_CODES`.

**Returns:** `bool`

---

### `_fetch_page(page_number: int, page_size: int) -> list[dict]`

Request one page of OPEN/FORTHCOMING calls from the search endpoint via HTTP POST with multipart form-data.

**Parameters:**

- `page_number` (`int`): 1-based page index to request.
- `page_size` (`int`): Number of results per page.

**Returns:** `list[dict]` — Raw result dicts from the `results` key of the API response.

**Raises:** `requests.HTTPError` — If the server returns a non-2xx status code.

---

### `fetch_open_and_forthcoming_calls(page_size: int = 50, max_pages: int | None = None) -> list[dict]`

Fetch all open and forthcoming English EU calls by paginating the API.

Stops when a page returns no results or `max_pages` is reached. Logs per-page keep/drop statistics.

**Parameters:**

- `page_size` (`int`, default `50`): Number of results to request per API page.
- `max_pages` (`int | None`, default `None`): Maximum number of pages to fetch. `None` means no limit; a `WARNING` is logged when the limit is hit.

**Returns:** `list[dict]` — Normalised call records filtered to OPEN/FORTHCOMING + English.

---

### `load(path: Path) -> list[dict]`

Load previously saved calls from a JSON file (cache fallback).

**Parameters:**

- `path` (`Path`): Path to the JSON file written by `save`.

**Returns:** `list[dict]` — Deserialised call records.

---

### `save(calls: list[dict], target_path: Path) -> None`

Persist call records as a pretty-printed UTF-8 JSON file.

**Parameters:**

- `calls` (`list[dict]`): Records to serialise.
- `target_path` (`Path`): Destination file path; parent directories are created automatically.

**Returns:** `None`
