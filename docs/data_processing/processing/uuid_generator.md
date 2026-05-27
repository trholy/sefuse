# `data_processing.processing.uuid_generator`

Deterministic UUID5 column generator for funding DataFrames.

---

## Class `UuidGenerator`

Generates deterministic UUID5 values from an existing DataFrame column using a fixed namespace.

### `__init__(namespace: uuid.UUID)`

**Parameters:**

- `namespace` (`uuid.UUID`): UUID namespace used as the base for `uuid.uuid5` generation. Both pipelines use `uuid.UUID("12345678-1234-5678-1234-567812345678")`.

---

### `add_uuid_column(df: pl.DataFrame, source_column: str, target_column: str = "uuid") -> pl.DataFrame`

Add a UUID5 column derived from an existing string column.

**Parameters:**

- `df` (`pl.DataFrame`): Input DataFrame.
- `source_column` (`str`): Column whose string values are passed to `uuid.uuid5` to produce deterministic IDs.
- `target_column` (`str`, default `"uuid"`): Name of the new UUID column appended to the DataFrame.

**Returns:** `pl.DataFrame` — DataFrame with the new UUID column (stored as `Utf8` strings) appended.
