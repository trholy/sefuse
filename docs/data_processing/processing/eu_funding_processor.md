# `data_processing.processing.eu_funding_processor`

Transforms raw EU API call records into the shared funding dataframe schema.

## Module Constants

- `EU_STATUS_FORTHCOMING`, `EU_STATUS_OPEN`, `EU_STATUS_CLOSED`: recognized EU status codes.
- `EU_ALLOWED_STATUS_CODES`: set of status codes eligible for processing.
- `UUID_SOURCE_COLUMN`: column name used as the deterministic UUID input.
- `MIN_DESCRIPTION_LENGTH`: minimum description length required to keep a record.
- `EU_COMMON_SCHEMA`: target Polars schema for the normalized EU dataset.

## Class `EuFundingProcessor`

Converts a list of EU API payload dictionaries into a normalized `polars.DataFrame`.

### Constructor

- `html_cleaner`: `HtmlCleaner` instance used for summary and description normalization.

### Internal Helpers

- `_normalize_string(value)`: returns stripped text or `None`.
- `_parse_status(status_code)`: marks open and forthcoming calls as active and closed calls as deleted.
- `_normalize_list(value)`: converts list-like or scalar values into a list of strings.
- `_parse_datetime(value)`: parses ISO-like timestamps into `datetime` objects.
- `_build_funding_area(keywords, identifier, call_id)`: removes duplicates and identifiers from keyword lists.
- `_compute_id_hash(uuid_source)`: builds an MD5 hash from the UUID source string.
- `_is_allowed_status(status_code)`: checks whether a status is processable.
- `_should_keep_item(...)`: filters out records with unsupported status, weak descriptions, or no usable keywords.

### `transform(eu_calls)`

Normalizes raw EU call items into the shared schema.

#### Behavior

1. Returns an empty dataframe with `EU_COMMON_SCHEMA` when no input is available.
2. Extracts identifiers, titles, summaries, dates, URLs, funding metadata, and keyword lists.
3. Cleans HTML-rich text and combines summary plus full description when both are meaningful.
4. Filters invalid or unusable records.
5. Maps each accepted record into the target schema, including `date_1`, `date_2`, and `deleted`.
6. Ensures every schema column exists and has the expected Polars dtype.

#### Returns

A `polars.DataFrame` ready for shared downstream processing.
