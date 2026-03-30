# `data_processing.processing.german_funding_processor`

Provides the German dataset transformation hook before shared cleanup and storage.

## Class `GermanFundingProcessor`

This processor currently performs a minimal schema adjustment because the German source data is already close to the target shape.

### `transform(df)`

Renames date columns to the shared names expected by the rest of the system:

- `on_website_from` -> `date_1`
- `last_updated` -> `date_2`

Returns the updated `polars.DataFrame`.
