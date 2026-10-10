# `shared.alert_levels`

Names and labels of the saved-search alert match levels.

Streamlit lets a user pick a level and FastAPI judges new programmes against it, so the names live in `shared/` to keep the two services in step. Only the names and labels are defined here. The rule behind each name — the rank a new programme must reach among the saved query's existing results, plus a per-collection noise floor — lives in FastAPI and is described in [Saved-Search Alerts](../fastapi/alerts.md).

---

## Constants

| Constant | Type | Value | Description |
|---|---|---|---|
| `LEVELS` | `tuple[str, ...]` | `("broad", "balanced", "strict")` | Level names, from most to least permissive. |
| `DEFAULT_LEVEL` | `str` | `"balanced"` | Level used when none, or an unknown one, is stored. |
| `LEVEL_LABELS` | `dict[str, str]` | see below | UI label per level. |

| Level | Label |
|---|---|
| `broad` | `Broad - among your top 25` |
| `balanced` | `Balanced - top 10` |
| `strict` | `Strict - top 3` |

The labels describe the default ranks. An operator who overrides them with `ALERT_LEVEL_RULES` changes the rule but not these labels.

---

## Functions

### `normalize_level(value: object) -> str`

Return `value` if it names a level, otherwise `DEFAULT_LEVEL`.

**Parameters:**

- `value` (`object`): Candidate level name, e.g. from a database row.

**Returns:** `str` — one of `LEVELS`.
