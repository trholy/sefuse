# `data_processing.processing.eu_funding_processor`

Transforms raw EU call dicts from the API into a typed Polars DataFrame.

---

## Module Constants

| Constant | Type | Value / Description |
|---|---|---|
| `UUID_SOURCE_COLUMN` | `str` | `"uuid_source_call_id"` — Temporary column holding the string used as UUID5 input; dropped before Parquet storage. |
| `MIN_DESCRIPTION_LENGTH` | `int` | `25` — Minimum character length of a cleaned description required to keep a record. |
| `EU_COMMON_SCHEMA` | `dict[str, pl.DataType]` | Polars schema defining all columns and dtypes for the normalised EU DataFrame (identifier, title, datetime, taxonomy list, contact, and `deleted` fields). |

---

## Class `EuFundingProcessor`

Transforms raw EU call dicts from the API into a typed Polars DataFrame. Filters out non-English calls with insufficient description or no keywords, normalises field types, and builds the shared `EU_COMMON_SCHEMA` used by downstream pipeline steps.

### `__init__(html_cleaner: HtmlCleaner)`

**Parameters:**

- `html_cleaner` (`HtmlCleaner`): Used to strip HTML from summary and `descriptionByte` fields.

---

### `_normalize_string(value: object) -> str | None`

Coerce `value` to a stripped string, returning `None` for blank inputs.

**Parameters:**

- `value` (`object`): Any value; `None` or whitespace-only strings return `None`.

**Returns:** `str | None` — Stripped string or `None`.

---

### `_parse_status(status_code: str) -> bool`

Return `True` (deleted) when `status_code` is not an active EU status.

**Parameters:**

- `status_code` (`str`): Raw status code from the API metadata.

**Returns:** `bool` — `True` if the call should be marked deleted, `False` if active.

---

### `_normalize_list(value: object) -> list[str]`

Coerce a scalar, collection, or `None` to a list of non-empty stripped strings.

**Parameters:**

- `value` (`object`): Scalar, list, tuple, set, or `None`.

**Returns:** `list[str]` — Flat list of non-empty strings.

---

### `_parse_datetime(value: object) -> datetime | None`

Parse an ISO 8601 datetime string to a timezone-naive `datetime`, or `None`.

**Parameters:**

- `value` (`object`): Raw value expected to match `"%Y-%m-%dT%H:%M:%S.%f%z"`.

**Returns:** `datetime | None` — Timezone-naive datetime, or `None` on parse failure.

---

### `_build_funding_area(keywords: list[str], identifier: str | None, call_id: str | None) -> list[str]`

Deduplicate `keywords`, removing entries that match the call `identifier` or `call_id`.

**Parameters:**

- `keywords` (`list[str]`): Raw keyword list from API metadata.
- `identifier` (`str | None`): Topic identifier blocked from appearing in funding area.
- `call_id` (`str | None`): Call identifier blocked from appearing in funding area.

**Returns:** `list[str]` — Deduplicated keyword list with identifier values removed.

---

### `_compute_id_hash(uuid_source: str) -> str`

Return the MD5 hex digest of `uuid_source` as a stable row identifier.

**Parameters:**

- `uuid_source` (`str`): String to hash (call ID, identifier, URL, or title).

**Returns:** `str` — 32-character MD5 hex digest.

---

### `_is_allowed_status(status_code: str | None) -> bool`

Return `True` when `status_code` is OPEN or FORTHCOMING.

**Parameters:**

- `status_code` (`str | None`): EU status code to check against `EU_ACTIVE_STATUS_CODES`.

**Returns:** `bool`

---

### `_should_keep_item(title: str, summary: str, cleaned_description_html: str, keywords: list[str], deadline: datetime | None, status_code: str | None) -> bool`

Return `True` when a call passes all retention checks: allowed status, minimum description length, and non-empty keyword list.

**Parameters:**

- `title` (`str`): Call title.
- `summary` (`str`): Cleaned summary text.
- `cleaned_description_html` (`str`): Cleaned full description; must be ≥ `MIN_DESCRIPTION_LENGTH` characters.
- `keywords` (`list[str]`): Deduplicated funding area keywords; must be non-empty.
- `deadline` (`datetime | None`): Parsed deadline (not used in retention checks).
- `status_code` (`str | None`): Must be in `EU_ACTIVE_STATUS_CODES`.

**Returns:** `bool` — `True` if the record should be retained.

---

### `transform(eu_calls: list[dict]) -> pl.DataFrame`

Convert a list of raw EU call dicts into a cleaned, typed DataFrame.

Rows that fail status, description-length, or keyword checks are dropped. Returns an empty DataFrame with `EU_COMMON_SCHEMA` if no rows survive.

**Parameters:**

- `eu_calls` (`list[dict]`): Raw call records as returned by `EuFundingFetcher.fetch_open_and_forthcoming_calls`.

**Returns:** `pl.DataFrame` — Typed DataFrame conforming to `EU_COMMON_SCHEMA`.
