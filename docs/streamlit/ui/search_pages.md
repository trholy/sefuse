# `streamlit.ui.search_pages`

Defines the reusable Streamlit page classes for German and EU funding search.

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

- `render_sidebar()`: returns semantic weight, search limit, and extra context.
- `render_result(result)`: renders one result card.

### Optional Hook

- `process_results(results, context)`: allows subclasses to post-process or filter results before rendering.

### `render()`

Builds the common page flow:

1. Configure the page.
2. Render the query text area.
3. Render sidebar controls through the subclass hook.
4. Execute backend search when the user clicks the search button.
5. Aggregate chunked backend results.
6. Apply optional result post-processing.
7. Render success, warning, or error feedback.

## Class `GermanFundingSearchPage`

Implements the German federal funding UI.

### Key Behavior

- Uses `/v1/search/german`.
- Loads filter options from text files in the `data` directory.
- Renders sidebar controls for location, funding type, eligible applicants, funding area, search limit, semantic weight, and `Drop N/A`.
- Applies result filtering through `apply_filters`.
- Renders cards with `render_german_project_result`.

## Class `EuFundingSearchPage`

Implements the EU funding UI.

### Key Behavior

- Uses `/v1/search/eu`.
- Provides search limit and semantic-weight sidebar controls.
- Does not apply extra filtering after retrieval.
- Renders cards with `render_eu_project_result`.
