# `streamlit.ui.search_pages`

Defines the abstract base class and concrete implementations for German and EU funding search pages.

---

## `_save_search_dialog(...)`

The "Save this search" dialog. It stores the query, collection, filters, semantic
weight and result limit, and optionally switches an alert on.

- **Match level, not a number** — `ui.alerts.render_alert_level_slider`, one slider over `shared.alert_levels.LEVELS`
  (Broad / Balanced / Strict, default Balanced) stores the level *name*. FastAPI
  decides what it means relative to the saved query; no cosine reaches the UI. See
  [Saved-Search Alerts](../../fastapi/alerts.md).
- **Duplicate guard** — `SavedSearchRepository.find_duplicate` is called before
  `create`: same user, collection, query text, filters and semantic weight means the
  same search, whatever its title or limit. The dialog then points at the existing
  entry instead of saving a second copy, which would push every alert twice. It is an
  application-level check, not a database constraint, so two concurrent saves can
  still both get through.
- Switching an alert on (off → on) resets `alert_baseline_at` to `NOW()`, so only
  programmes indexed from that moment can alert.

---

## Class `BaseFundingSearchPage`

Abstract base class for funding search pages. Subclasses define the API endpoint, widget keys, sidebar controls, and result rendering. The shared `render()` method wires them together.

### `BaseFundingSearchPage(model: str | None = None, fastapi_url: str | None = None)`

**Parameters:**

- `model` (`str | None`, default `None`): Embedding model name. Falls back to the `MODEL` environment variable, then `"bge-m3"`.
- `fastapi_url` (`str | None`, default `None`): FastAPI base URL. Falls back to the `FASTAPI_URL` environment variable, then `"http://fastapi:8000"`.

---

### Abstract properties

| Property | Type | Description |
|---|---|---|
| `search_endpoint` | `str` | FastAPI endpoint path, e.g. `"/v1/search/german"`. |
| `search_button_key` | `str` | Unique Streamlit widget key for the search button. |
| `query_key` | `str` | Unique Streamlit widget key for the query text area. |

---

### `search_limit_key -> str`

Streamlit widget key for the search-limit number input; derived automatically from `search_button_key`.

**Returns:** `str`

---

### `no_results_message -> str`

Message displayed when the backend returns zero matches.

**Returns:** `str` — default `"No projects found."`, overridden by `GermanFundingSearchPage`.

---

### `render_sidebar() -> tuple[float, int, dict[str, Any]]`

Abstract. Render sidebar controls and return the search configuration.

**Returns:** `tuple[float, int, dict[str, Any]]` — `(semantic_weight, search_limit, context)` where `context` may contain a `filters` key forwarded to the FastAPI backend.

---

### `render_result(result: dict[str, Any]) -> None`

Abstract. Render a single search result as a Streamlit card.

**Parameters:**

- `result` (`dict[str, Any]`): Project dict returned by the search backend.

**Returns:** `None`

---

### `render() -> None`

Render the full search page: query text area, sidebar controls, search button, and result cards.

Page config is not set here: under `st.navigation` only the entry point may call `st.set_page_config`, so the browser tab title comes from the `st.Page` title declared in [`build_navigation_pages()`](navigation.md).

On button click, calls `search_projects()` with all parameters (including `filters` from context). Renders success/warning/error feedback and iterates results through `render_result()`. Exceptions are caught and shown via `st.error(friendly_search_error(...))`.

**Returns:** `None`

---

## Class `GermanFundingSearchPage`

Search page for the German federal funding database. Adds taxonomy-based sidebar multiselect filters fetched from `/v1/vocab/german`.

**Inherits:** `BaseFundingSearchPage`

### Properties

| Property | Value |
|---|---|
| `search_endpoint` | `"/v1/search/german"` |
| `search_button_key` | `"search_federal"` |
| `query_key` | `"federal_query"` |
| `no_results_message` | `"No projects match your selected filters."` |

### `source_attribution`

Class attribute on `BaseFundingSearchPage`, default `None`. When set, `render()` writes it once as an `st.caption` below the results list.

`GermanFundingSearchPage` sets it: the Förderdatenbank programme texts are licensed CC BY-ND 4.0 with the Bundesministerium für Wirtschaft und Energie as rights holder, and displaying them in search results is republication, which the licence requires attribution for. Each row additionally carries its own attribution string in the `license_info` payload field.

---

### `FIELD_CONFIG`

Class-level list of `(field, label, widget_key)` triples for the four taxonomy filter fields:

| `field` | `label` | `widget_key` |
|---|---|---|
| `funding_location` | `"Funding location"` | `"federal_locations"` |
| `funding_type` | `"Type of funding"` | `"federal_funding_type"` |
| `eligible_applicants` | `"Eligible applicants"` | `"federal_eligible"` |
| `funding_area` | `"Funding area"` | `"federal_funding_area"` |

---

### `render_sidebar() -> tuple[float, int, dict[str, Any]]`

Render German-specific sidebar with taxonomy multiselects, search-limit number input, and semantic-weight slider.

Fetches the taxonomy artifact from `/v1/vocab/german` via `fetch_german_taxonomy()`. Falls back gracefully with a sidebar warning when the taxonomy is unavailable. Displays canonical labels while storing stable taxonomy keys internally.

**Returns:** `tuple[float, int, dict[str, Any]]` — `(semantic_weight, search_limit, context)` where `context["filters"]` contains the selected taxonomy keys.

---

### `render_result(result: dict[str, Any]) -> None`

Render a single German funding project by delegating to `render_german_project_result()`.

**Parameters:**

- `result` (`dict[str, Any]`): Project dict returned by the search backend.

**Returns:** `None`

---

## Class `EuFundingSearchPage`

Search page for EU funding calls. Provides a minimal sidebar (search limit and semantic weight slider) with no taxonomy filters.

**Inherits:** `BaseFundingSearchPage`

### Properties

| Property | Value |
|---|---|
| `search_endpoint` | `"/v1/search/eu"` |
| `search_button_key` | `"search_eu"` |
| `query_key` | `"eu_query"` |

---

### `render_sidebar() -> tuple[float, int, dict[str, Any]]`

Render EU-specific sidebar with search-limit number input and semantic-weight slider.

**Returns:** `tuple[float, int, dict[str, Any]]` — `(semantic_weight, search_limit, {})` where the context dict is empty (no taxonomy filters for EU searches).

---

### `render_result(result: dict[str, Any]) -> None`

Render a single EU funding call by delegating to `render_eu_project_result()`.

**Parameters:**

- `result` (`dict[str, Any]`): Project dict returned by the search backend.

**Returns:** `None`
