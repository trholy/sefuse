# `data_processing.utils.eu_funding_fetcher`

Fetches EU funding calls from the public search API and normalizes raw response metadata into a simpler application format.

## Module Constants

- `EU_STATUS_FORTHCOMING`, `EU_STATUS_OPEN`, `EU_STATUS_CLOSED`: supported EU call status codes.
- `EU_ALLOWED_STATUS_CODES`: allowed statuses during fetch-time filtering.

## Class `EuFundingFetcher`

### Constructor

- `api_url`: EU API endpoint.
- `api_key`: request API key.
- `timeout_seconds`: HTTP timeout per request.
- `page_delay_seconds`: delay inserted between paginated requests.

### Internal Helpers

- `_get_meta_value(meta, key)`: extracts a single normalized string from metadata.
- `_first_string(value)`: recursively finds the first useful scalar text value.
- `_normalize_meta_list(meta, key)`: converts metadata values into a list of strings.
- `_build_portal_topic_url(identifier)`: builds the public EU portal URL for a call.
- `_is_english(result_language, metadata_languages)`: accepts only English-language results.
- `_is_allowed_status(status_code)`: validates supported status codes.
- `_fetch_page(page_number, page_size)`: performs one HTTP POST request against the EU search endpoint.

### `fetch_open_and_forthcoming_calls(page_size=50, max_pages=100)`

Retrieves paginated EU call records and normalizes the fields consumed later by `EuFundingProcessor`.

#### Workflow

1. Request one API page at a time.
2. Stop when an empty page is returned or `max_pages` is reached.
3. Filter out unsupported statuses and non-English items.
4. Build simplified call dictionaries with identifiers, titles, dates, summaries, keywords, and URLs.
5. Log per-page keep/drop statistics.

Returns `list[dict]`.

### `load(path)`

Loads previously saved call data from JSON.

### `save(calls, target_path)`

Saves normalized call data to formatted UTF-8 JSON and creates parent directories when needed.
