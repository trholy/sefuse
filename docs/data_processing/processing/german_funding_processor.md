# `data_processing.processing.german_funding_processor`

German-funding-specific processing hook for date column normalisation before shared pipeline steps.

---

## Class `GermanFundingProcessor`

Minimal schema adjustment for the German funding dataset. The German source data is already close to the target shape, so this processor only renames the two date columns.

### `transform(df: pl.DataFrame) -> pl.DataFrame`

Rename German-specific date columns to the shared `date_1`/`date_2` schema.

**Parameters:**

- `df` (`pl.DataFrame`): Raw German funding DataFrame with `on_website_from` and `last_updated` columns.

**Returns:** `pl.DataFrame` — DataFrame with columns renamed: `on_website_from` → `date_1`, `last_updated` → `date_2`.
