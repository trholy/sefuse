# `data_processing.processing.cleaner`

Provides HTML cleanup and dataframe-wide text normalization for funding datasets.

## Classes

### `HtmlCleaner`

Converts raw text or HTML fragments into cleaned plain text.

#### `clean(value)`

- Returns `"N/A"` for missing or empty values.
- Parses HTML content with BeautifulSoup when tags are detected.
- Strips whitespace from plain strings.

### `DataCleaner`

Applies column-level cleanup rules to a Polars dataframe.

#### Constructor

- `html_cleaner`: `HtmlCleaner` instance used for string normalization.

#### `clean_dataframe(df)`

Performs the shared cleanup pipeline:

1. Extracts short and full descriptions from HTML sections in the `description` column.
2. Preserves already existing `project_short_description` and `project_full_description` values when present.
3. Replaces empty strings with nulls and then fills nulls with `"N/A"`.
4. Applies `HtmlCleaner.clean` to every UTF-8 column in the dataframe.

Returns a cleaned `polars.DataFrame`.
