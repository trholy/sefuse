# `data_processing.processing.uuid_generator`

Generates deterministic UUIDs for dataframe rows based on a stable source column.

## Class `UuidGenerator`

### Constructor

- `namespace`: `uuid.UUID` namespace used for UUIDv5 generation.

### `add_uuid_column(df, source_column, target_column="uuid")`

Adds a UUID column to a `polars.DataFrame`.

#### Behavior

- Reads values from `source_column`.
- Uses UUIDv5 with the configured namespace to produce deterministic IDs.
- Stores the generated value in `target_column`, which defaults to `uuid`.

#### Returns

A new `polars.DataFrame` with the UUID column added.
