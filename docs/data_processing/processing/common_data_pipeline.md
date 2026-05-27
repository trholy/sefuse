# `data_processing.processing.common_data_pipeline`

Shared clean → taxonomy → UUID → Parquet pipeline used by both the German and EU funding flows.

---

## Module Constant

| Constant | Type | Default | Description |
|---|---|---|---|
| `DEFAULT_EXPORT_COLUMNS` | `list[str]` | `["funding_type", "funding_area", "funding_location", "eligible_applicants"]` | Taxonomy columns canonicalised when `export_columns` is not explicitly provided. |

---

## Class `CommonDataPipeline`

Shared processing pipeline: clean → canonicalise taxonomy → assign UUIDs → save Parquet outputs.

Used by both the German and EU funding pipelines. Taxonomy canonicalisation is handled by `TaxonomyContractBuilder`; a default instance is created if none is provided.

### `__init__(cleaner: DataCleaner, uuid_generator: UuidGenerator, taxonomy_builder: TaxonomyContractBuilder | None = None)`

**Parameters:**

- `cleaner` (`DataCleaner`): Cleans HTML and normalises string columns.
- `uuid_generator` (`UuidGenerator`): Derives deterministic UUID5s from a source column.
- `taxonomy_builder` (`TaxonomyContractBuilder | None`, default `None`): Builds and saves the taxonomy contract. A fresh `TaxonomyContractBuilder()` is created when `None`.

---

### `process_and_store(df: pl.DataFrame, cleaned_path: Path, uuid_path: Path, source_column: str, data_dir: Path, taxonomy_path: Path, export_columns: list[str] | None = None, columns_to_drop_before_store: list[str] | None = None, taxonomy_domain: str = "german") -> None`

Run the full clean → taxonomy → UUID → write pipeline and save outputs.

Writes three artefacts to disk: cleaned Parquet, UUID Parquet, and the taxonomy JSON contract.

**Parameters:**

- `df` (`pl.DataFrame`): Raw or pre-processed input DataFrame.
- `cleaned_path` (`Path`): Destination for the cleaned Parquet file (parent dirs created automatically).
- `uuid_path` (`Path`): Destination for the UUID-enriched Parquet file.
- `source_column` (`str`): Column whose values are hashed via UUID5 to generate deterministic UUIDs.
- `data_dir` (`Path`): Root data directory; created if absent.
- `taxonomy_path` (`Path`): Destination for the taxonomy JSON artifact.
- `export_columns` (`list[str] | None`, default `None`): Taxonomy columns to canonicalise. Defaults to `DEFAULT_EXPORT_COLUMNS` when `None`.
- `columns_to_drop_before_store` (`list[str] | None`, default `None`): Columns removed from both Parquet files before writing (e.g. the UUID source column for EU data).
- `taxonomy_domain` (`str`, default `"german"`): Domain label embedded in the taxonomy artifact (`"german"` or `"eu"`).

**Returns:** `None`
