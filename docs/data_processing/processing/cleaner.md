# `data_processing.processing.cleaner`

HTML cleaning and DataFrame normalisation utilities for funding data pipelines.

---

## Class `HtmlCleaner`

Strips HTML tags from a string, returning plain text.

### `clean(value: str | None) -> str`

Strip HTML markup and return plain text.

**Parameters:**

- `value` (`str | None`): Raw string, optionally containing HTML tags.

**Returns:** `str` — Plain text with tags removed, or `"N/A"` for empty/`None` input.

---

## Class `DataCleaner`

Cleans a raw funding DataFrame: extracts description sections, fills nulls, and strips HTML from all string columns.

### `__init__(html_cleaner: HtmlCleaner)`

**Parameters:**

- `html_cleaner` (`HtmlCleaner`): Instance used to strip HTML from string columns.

---

### `clean_dataframe(df: pl.DataFrame) -> pl.DataFrame`

Apply all cleaning steps to a funding DataFrame.

Extracts `project_short_description` and `project_full_description` from the HTML `description` column using German `<h3>Kurztext</h3>` / `<h3>Volltext</h3>` section markers. Preserves already-populated values (e.g. from EU input) by using `pl.coalesce`. Replaces empty strings with `null` and fills `null` with `"N/A"`. Applies `HtmlCleaner.clean` to all remaining `Utf8` columns.

**Parameters:**

- `df` (`pl.DataFrame`): Raw input DataFrame with at least a `description` column.

**Returns:** `pl.DataFrame` — Cleaned DataFrame with description fields populated and all string columns HTML-stripped.
