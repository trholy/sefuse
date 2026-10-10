# `streamlit.app_pages.4_Watchlist`

Entry-point script for the per-user watchlist page.

Programmes are added to the watchlist from the search pages, where every result carries an **Add to Watchlist** checkbox (see [Search Pages](../ui/search_pages.md)). This page lists what the logged-in user has bookmarked and lets them remove entries.

This module contains no function or class definitions. It executes the following steps at import time:

| Step | Action |
|---|---|
| 1 | `require_page_access("Watchlist", ...)` — runs the auth gate and returns the user's id. With `AUTH_ENABLED=false` the page explains that the watchlist requires authentication and stops. |
| 2 | Loads the user's entries with `WatchlistRepository.list_items(user_id)`, newest first. |
| 3 | With no entries, shows an info message and stops. |
| 4 | Splits the entries by `collection_type` and renders them under **Federal Funding** and **EU Funding**; an empty group is skipped. |
| 5 | Renders each entry as its title (linked to the programme's website when one is stored), the time it was added, and a **Remove** button. |

**Remove** calls `WatchlistRepository.remove(user_id, project_id, collection_type)` and reruns the page.

The watchlist stores the programme's id, title and website at the time it was added (see [Repositories](../auth/repositories.md)). An entry therefore stays visible after the programme has left the search index.
