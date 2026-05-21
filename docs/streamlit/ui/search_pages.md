# `streamlit.ui.search_pages`

Defines reusable Streamlit page classes for German and EU funding search.

## Class `BaseFundingSearchPage`

Abstract base class for funding search pages.

### Constructor

- `model`: embedding model name, defaults from `MODEL`.
- `fastapi_url`: backend base URL, defaults from `FASTAPI_URL`.

### Abstract Properties

- `page_title`
- `search_endpoint`
- `search_button_key`
- `query_key`

### Concrete Properties

- `search_limit_key`: derived Streamlit widget key for result limit.
- `no_results_message`: default message shown when no matches are found.

### Abstract Methods

- `render_sidebar()`: returns search limit and additional context.
- `render_result(result)`: renders one result card.

### Optional Hook

- `process_results(results, context)`: allows subclasses to post-process results before rendering.

### `render()`

Common page flow:

1. Configure page metadata.
2. Render query input.
3. Render sidebar controls through subclass hook.
4. Execute backend search on button click.
5. Aggregate chunk-level matches.
6. Apply optional post-processing.
7. Render success/warning/error feedback.

## Class `GermanFundingSearchPage`

Implements the German federal funding UI.

### Key Behavior

- Uses `/v1/search/german`.
- Fetches taxonomy from FastAPI (`/v1/vocab/german`) and builds filter widgets from taxonomy keys.
- Displays canonical labels in multiselect controls while storing stable taxonomy keys.
- Sends selected taxonomy keys to backend search as `filters`.
- Applies key-based result filtering through `apply_filters`.
- Warns in sidebar when taxonomy loading fails.

## Class `EuFundingSearchPage`

Implements the EU funding UI.

### Key Behavior

- Uses `/v1/search/eu`.
- Provides search-limit sidebar control.
- Renders cards with `render_eu_project_result`.
