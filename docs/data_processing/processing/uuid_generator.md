# UUID Generator Module

Utility class for generating deterministic UUIDs based on input values. This module ensures consistent, reproducible unique identifiers for data records.

---

## UuidGenerator

Class for generating UUID5 identifiers based on input values and a fixed namespace.

### Constructor (__init__ method)

Initializes the UUID generator with a fixed namespace.

#### Parameters

- `namespace` (uuid.UUID): The UUID namespace to use for generating deterministic UUIDs.

#### Attributes

- `_namespace` (uuid.UUID): The namespace used for UUID generation

### Methods

#### add_uuid_column

Adds a deterministic UUID column to a Polars DataFrame based on a source column.

##### Parameters

- `df` (pl.DataFrame): Input DataFrame to process.
- `source_column` (str): Name of the column to use as input for UUID generation.
- `target_column` (str, optional): Name of the new UUID column to create. Default is `"uuid"`.

##### Returns

- `pl.DataFrame`: DataFrame with the new UUID column added.
