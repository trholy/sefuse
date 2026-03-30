# `shared.taxonomy_contract`

Defines shared taxonomy normalization and scoring helpers used consistently across data processing, backend, and frontend modules.

## Constants

- `TAXONOMY_FALLBACK_VALUE`: fallback display value (`"Unknown"`).
- `TAXONOMY_FALLBACK_KEY`: fallback normalized key (`"unknown"`).

## Functions

### `normalize_taxonomy_key(value)`

Normalizes a value into a stable taxonomy key:

- lowercases
- replaces German umlauts/ß
- removes diacritics
- normalizes separators (`space`, `-`, `&`, `/`) to `_`
- removes non-word characters

### `is_invalid_taxonomy_value(value, key)`

Marks null-like/empty/very-short values as invalid taxonomy inputs.

### `score_taxonomy_display_value(value)`

Scores display candidates to prefer human-readable canonical labels.

### `taxonomy_key_set(values)`

Converts iterable input values into a normalized key set, skipping empty/null entries.
