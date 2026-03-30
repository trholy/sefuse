# `data_processing.processing.value_extractor`

Extracts stable, human-readable unique values from dataframe columns and saves them for UI filters.

## Class `UniqueValueExtractor`

### Class Constant

- `FALLBACK`: value appended when invalid or empty source entries are encountered.

### Internal Helpers

- `_normalize(value)`: normalizes text for deduplication by lowercasing, replacing umlauts, removing accents, and standardizing separators.
- `_is_invalid(value, key)`: detects null-like, empty, or uninformative values that should map to the fallback bucket.
- `_score(value)`: ranks duplicate candidates so the most readable representation is kept.

### `extract(df, column)`

Builds a sorted list of unique display values for a dataframe column.

#### Behavior

- Supports both scalar string columns and list columns.
- Deduplicates using normalized keys.
- Keeps the best-looking original representation for each normalized key.
- Appends `Unknown` when invalid values were encountered.

Returns `list[str]`.

### `save(values, target_path)`

Writes extracted values to a UTF-8 text file with one value per line.
