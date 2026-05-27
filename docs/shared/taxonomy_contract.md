# `shared.taxonomy_contract`

Shared taxonomy normalization and key helpers used consistently across data processing, FastAPI backend, and Streamlit frontend.

---

## Constants

| Constant | Type | Value | Description |
|---|---|---|---|
| `TAXONOMY_FALLBACK_VALUE` | `str` | `"Unknown"` | Display value used when a taxonomy entry is invalid or unrecognised. |
| `TAXONOMY_FALLBACK_KEY` | `str` | `"unknown"` | Normalised key corresponding to `TAXONOMY_FALLBACK_VALUE`. |

---

## Functions

### `normalize_taxonomy_key(value: str | None) -> str`

Convert a raw taxonomy display value to a stable, ASCII lookup key.

Pipeline: lowercase → umlaut expansion (`ä→ae`, `ö→oe`, `ü→ue`, `ß→ss`) → NFKD normalisation and combining-character removal → separator normalisation (space, `-`, `&`, `/` → `_`) → non-word character removal → strip leading/trailing underscores.

**Parameters:**

- `value` (`str | None`): Raw display value, e.g. `"Forschung & Entwicklung"`.

**Returns:** `str` — normalised key, e.g. `"forschung_entwicklung"`. Returns `""` for `None`.

**Example:**

```python
normalize_taxonomy_key("Förderung") == "foerderung"
normalize_taxonomy_key(None) == ""
```

---

### `is_invalid_taxonomy_value(value: str | None, key: str) -> bool`

Return `True` if a taxonomy value should be routed to the fallback bucket.

A value is invalid when its normalised key is empty, null-like (`"none"`, `"nan"`, `""`, `"null"`), or shorter than three characters.

**Parameters:**

- `value` (`str | None`): Original display value.
- `key` (`str`): Pre-computed normalised key from `normalize_taxonomy_key`.

**Returns:** `bool` — `True` if the value should be treated as unknown/invalid.

---

### `score_taxonomy_display_value(value: str | None) -> int`

Score a display value candidate for canonical-name selection (higher = preferred).

Rewards mixed-case (`+2`) and spaced values (`+2`); penalises underscored (`-1`) and all-lowercase values (`-1`). Used by `TaxonomyContractBuilder` to pick the best alias as the canonical label for each taxonomy key.

**Parameters:**

- `value` (`str | None`): Display string to score.

**Returns:** `int` — relative score; `-1` for `None`.

---

### `taxonomy_key_set(values: Iterable[object] | None) -> set[str]`

Convert an iterable of raw taxonomy values to a set of normalised keys.

Used by both FastAPI (filter matching) and Streamlit (sidebar filter comparison) to ensure consistent normalisation across services.

**Parameters:**

- `values` (`Iterable[object] | None`): Raw taxonomy strings or mixed types. `None` and empty strings are silently skipped.

**Returns:** `set[str]` — set of normalised keys produced by `normalize_taxonomy_key`.

**Example:**

```python
taxonomy_key_set(["Zuschuss", "Darlehen"]) == {"zuschuss", "darlehen"}
taxonomy_key_set(None) == set()
```
