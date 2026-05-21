# `streamlit.ui.search_pages`

Defines reusable Streamlit page classes for German and EU funding search.

## Class `BaseFundingSearchPage`

Abstract base class for funding search pages.

### Constructor

- `model`: embedding model name, defaults from `MODEL` env var.
- `fastapi_url`: backend base URL, defaults from `FASTAPI_URL` env var.

### Abstract Properties

- `page_title`
- `search_endpoint`
- `search_button_key`
- `query_key`

### Concrete Properties

- `search_limit_key`: derived Streamlit widget key for result limit.
- `no_results_message`: default message shown when no matches are found.

### Abstract Methods

- `render_sidebar()`: renders page-specific sidebar controls and returns `(semantic_weight: float, search_limit: int, context: dict)` where *context* may contain a `filters` key forwarded to the FastAPI backend.
- `render_result(result)`: renders one result card.

### `render()`

Common page flow:

1. Configure page metadata.
2. Render query text area.
3. Call `render_sidebar()` to get search parameters and filter context.
4. On button click, call `search_projects()` with all parameters (including `filters` from context).
5. Render success/warning/error feedback and iterate results through `render_result()`.

All taxonomy filtering and drop-N/A logic is handled server-side by the FastAPI backend.

## Class `GermanFundingSearchPage`

Implements the German federal funding UI.

### `render_sidebar()`

Fetches the taxonomy artifact from `/v1/vocab/german` and builds multiselect filter widgets for each field in `FIELD_CONFIG`. Displays canonical labels while storing stable taxonomy keys internally. Falls back gracefully with a sidebar warning when the taxonomy is unavailable. Returns `(semantic_weight, search_limit, context)` where *context* contains a `filters` dict with selected taxonomy keys and the `drop_na` flag.

### Key Behavior

- Uses `/v1/search/german`.
- Sends selected taxonomy keys and drop-N/A flag to the backend as `filters` in each search request.
- Sidebar also exposes search limit, semantic weight slider, and drop-N/A checkbox.

## Class `EuFundingSearchPage`

Implements the EU funding UI.

### `render_sidebar()`

Renders search limit and semantic weight slider controls. Returns `(semantic_weight, search_limit, context)` where *context* is an empty dict (no taxonomy filters for EU searches).

### Key Behavior

- Uses `/v1/search/eu`.
- Renders cards with `render_eu_project_result`.
