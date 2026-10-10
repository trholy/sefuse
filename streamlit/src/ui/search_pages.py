import os
import logging
from abc import ABC, abstractmethod
from typing import Any

import streamlit as st

from auth.constants import SESSION_USER_ID
from shared.alert_levels import DEFAULT_LEVEL

from ui.alerts import render_alert_level_slider
from ui.search_state import (
    EU_QUERY_KEY,
    FEDERAL_QUERY_KEY,
    RESTORE_KEY,
    RestorePayload,
    SearchState,
)
from auth.handlers import (
    alerts_enabled,
    get_watchlist_repository,
    get_saved_search_repository,
    is_auth_enabled,
    is_authenticated,
)
from utils import (
    fetch_german_taxonomy,
    render_eu_project_result,
    render_german_project_result,
    search_projects,
    friendly_search_error,
)

logger = logging.getLogger(__name__)


@st.dialog("Save Search")
def _save_search_dialog(
    collection_type: str,
    query_text: str,
    filters: dict,
    semantic_weight: float,
    search_limit: int,
    user_id: int,
) -> None:
    title = st.text_input("Search title", max_chars=128)

    # With ALERTS_ENABLED off the search is still worth saving — it is restored
    # from the Saved Searches page — so only the alert half of the dialog goes.
    alerts_on = alerts_enabled()
    alert_enabled = False
    level = DEFAULT_LEVEL
    if alerts_on:
        alert_enabled = st.checkbox(
            "Enable alerts",
            value=True,
            help=(
                "Check daily for new fundings matching this search. "
                "You can change this later on the Saved Searches page."
            ),
        )
        level = render_alert_level_slider(disabled=not alert_enabled)

    if st.button("Confirm Save"):
        if not title.strip():
            st.error("Please enter a title.")
            return
        try:
            selected_filters = {
                k: v for k, v in filters.items()
                if isinstance(v, bool) or v
            }
            repo = get_saved_search_repository()
            existing = repo.find_duplicate(
                user_id=user_id,
                query_text=query_text,
                collection_type=collection_type,
                filters=selected_filters,
                semantic_weight=semantic_weight,
            )
            if existing:
                st.warning(
                    f"You already saved this search as **{existing.title}**. "
                    f"Manage it on the **Saved Searches** page."
                )
                return
            search_id = repo.create(
                user_id=user_id,
                title=title.strip(),
                query_text=query_text,
                collection_type=collection_type,
                filters=selected_filters,
                semantic_weight=semantic_weight,
                search_limit=search_limit,
            )
            if alerts_on:
                repo.update_alert_config(
                    search_id=search_id,
                    user_id=user_id,
                    alert_enabled=alert_enabled,
                    alert_level=level,
                )
            if alert_enabled:
                st.success(
                    f"Search **{title}** saved with alerts on. New matches "
                    f"will appear on the **Saved Searches** page."
                )
            elif alerts_on:
                st.success(
                    f"Search **{title}** saved. Go to the "
                    f"**Saved Searches** page to restore it or "
                    f"turn on alerts."
                )
            else:
                st.success(
                    f"Search **{title}** saved. Go to the "
                    f"**Saved Searches** page to restore it."
                )
        except Exception:
            logger.warning("Failed to save search", exc_info=True)
            st.error("Could not save search. Please try again.")


class BaseFundingSearchPage(ABC):
    """Abstract base class for German and EU funding search pages.

    Subclasses define the page title, API endpoint, widget keys, sidebar controls,
    and result rendering. The shared `render()` method wires them together.

    Subclasses may set `source_attribution` to a markdown string; `render()` shows it
    once below the results as the source/licence credit for the data displayed.

    Args:
        model (str | None, default=None): Embedding model name; falls back to the
            `MODEL` environment variable (`"bge-m3"`).
        fastapi_url (str | None, default=None): FastAPI base URL; falls back to the
            `FASTAPI_URL` environment variable (`"http://fastapi:8000"`).
    """

    # Source/licence credit for the displayed data. None means nothing is shown.
    source_attribution: str | None = None

    def __init__(
        self,
        model: str | None = None,
        fastapi_url: str | None = None,
    ):
        """Initialise shared configuration from arguments or environment variables.

        Args:
            model (str | None, optional): Embedding model name. Defaults to the
                ``MODEL`` environment variable or ``"bge-m3"``.
            fastapi_url (str | None, optional): FastAPI base URL. Defaults to the
                ``FASTAPI_URL`` environment variable or ``"http://fastapi:8000"``.
        """
        self.model = model or os.getenv("MODEL", "bge-m3")
        self.fastapi_url = fastapi_url or os.getenv(
            "FASTAPI_URL",
            "http://fastapi:8000",
        )

    @property
    @abstractmethod
    def search_endpoint(self) -> str:
        """FastAPI endpoint path for this collection, e.g. ``"/v1/search/german"``."""

    @property
    @abstractmethod
    def search_button_key(self) -> str:
        """Unique Streamlit widget key for the search button."""

    @property
    @abstractmethod
    def query_key(self) -> str:
        """Unique Streamlit widget key for the query text area."""

    @property
    @abstractmethod
    def collection_type(self) -> str:
        """Collection identifier for watchlist scoping: ``'german'`` or ``'eu'``."""

    @property
    def search_limit_key(self) -> str:
        """Streamlit widget key for the search-limit number input."""
        return f"{self.search_button_key}_limit"

    @property
    def results_key(self) -> str:
        """Session-state key for caching search results across reruns."""
        return f"{self.search_button_key}_results"

    @property
    def no_results_message(self) -> str:
        """Message displayed when the backend returns zero matches."""
        return "No projects found."

    def _render_common_sidebar_controls(self) -> tuple[float, int]:
        """Render the search-limit and semantic-weight sidebar widgets.

        Shared between ``GermanFundingSearchPage`` and ``EuFundingSearchPage``
        to avoid duplicating the two common controls. Restoration of saved
        values is handled by callers setting session state keys directly
        before this method runs.

        Returns:
            tuple[float, int]: ``(semantic_weight, search_limit)``
        """
        search_limit = st.sidebar.number_input(
            "Search limit",
            min_value=5,
            max_value=50,
            value=10,
            step=5,
            key=self.search_limit_key,
        )

        semantic_weight = st.sidebar.slider(
            "Keyword vs Semantic Weight",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.05,
            key=f"{self.search_button_key}_semantic_weight",
            help="0 = pure keyword search, 1 = pure semantic search.",
        )

        return float(semantic_weight), int(search_limit)

    @abstractmethod
    def render_sidebar(self) -> tuple[float, int, dict[str, Any]]:
        """Render sidebar controls and return the search configuration.

        Subclasses implement this to provide page-specific sidebar widgets
        (filters, sliders, checkboxes) and return the collected parameters
        needed by the search request.

        Returns:
            tuple[float, int, dict[str, Any]]: A three-element tuple of
                ``(semantic_weight, search_limit, context)`` where *context*
                is a dict that may contain a ``filters`` key forwarded to the
                FastAPI backend.
        """
        pass

    @abstractmethod
    def render_result(self, result: dict[str, Any], rank: int | None = None) -> None:
        """Render a single search result as a Streamlit card.

        Args:
            result (dict[str, Any]): Project dict returned by the search backend.
            rank (int | None, default=None): 1-based position in the result list,
                shown in the card's relevance line.
        """

    def _consume_restore(self) -> RestorePayload | None:
        """Pop the one-shot restore payload and apply the controls both pages share.

        Popped here rather than in each subclass: the EU page used to leave the German
        page's filter payload behind, because it only removed the two keys it cared
        about. One key consumed in one place cannot drift like that.

        The clamps are applied here too, so a saved search whose stored weight or limit
        is out of range cannot put a widget into a state Streamlit will reject.

        Returns:
            RestorePayload | None: The payload, so a subclass can apply the parts only
                it understands, or ``None`` when nothing is being restored.
        """
        payload: RestorePayload | None = st.session_state.pop(RESTORE_KEY, None)
        if payload is None:
            return None
        if payload.semantic_weight is not None:
            st.session_state[f"{self.search_button_key}_semantic_weight"] = float(
                max(0.0, min(1.0, payload.semantic_weight))
            )
        if payload.limit is not None:
            st.session_state[self.search_limit_key] = int(
                max(5, min(50, payload.limit))
            )
        return payload

    def _clear_cached_results(self) -> None:
        """Remove the cached search so the page starts fresh."""
        st.session_state.pop(self.results_key, None)

    def render(self) -> None:
        """Render the full search page: text area, sidebar, search button, and results.

        Page config is not set here: under ``st.navigation`` only the entrypoint may
        call ``st.set_page_config``, so the browser tab title comes from the
        ``st.Page`` title declared in ``Home.build_navigation_pages``.
        """
        cached: SearchState | None = st.session_state.get(self.results_key)
        # Streamlit garbage-collects a widget's state when the widget is not rendered,
        # so navigating away and back empties the text area even though the results
        # survived. Put the query back before the widget is drawn.
        if cached is not None and cached.query and self.query_key not in st.session_state:
            st.session_state[self.query_key] = cached.query

        query = st.text_area(
            "Enter your project description:",
            height=100,
            max_chars=5000,
            placeholder="Start typing...",
            key=self.query_key,
        )
        semantic_weight, search_limit, context = self.render_sidebar()

        has_results = cached is not None
        can_save = is_auth_enabled() and is_authenticated() and has_results
        search_col, clear_col, save_col = st.columns(3)
        with search_col:
            search_clicked = st.button("Search", key=self.search_button_key)
        with clear_col:
            clear_clicked = st.button("Clear", key=f"{self.search_button_key}_clear")
        with save_col:
            save_clicked = st.button(
                "Save Search",
                key=f"save_btn_{self.search_button_key}",
                disabled=not can_save,
            )

        if clear_clicked:
            self._clear_cached_results()
            st.session_state.pop(self.query_key, None)
            st.rerun()

        if save_clicked:
            user_id = st.session_state.get(SESSION_USER_ID)
            # Saved from the cached search, not from the live sidebar: the user may
            # have moved a slider since, and what gets saved must be what produced the
            # results on screen.
            _save_search_dialog(
                collection_type=self.collection_type,
                query_text=cached.query if cached else "",
                filters=cached.filters if cached else {},
                semantic_weight=cached.weight if cached else 0.7,
                search_limit=cached.limit if cached else 20,
                user_id=user_id,
            )

        if search_clicked and query:
            try:
                results, weak_match = search_projects(
                    fastapi_url=self.fastapi_url,
                    model=self.model,
                    query=query,
                    search_limit=search_limit,
                    semantic_weight=semantic_weight,
                    endpoint=self.search_endpoint,
                    filters=context.get("filters"),
                )
                st.session_state[self.results_key] = SearchState(
                    results=results,
                    query=query,
                    context=context,
                    weight=semantic_weight,
                    limit=search_limit,
                    weak_match=weak_match,
                )
                st.rerun()
            except Exception as error:
                logger.exception("Search request failed: %s", error)
                st.error(friendly_search_error(error))

        state: SearchState | None = st.session_state.get(self.results_key)
        results = state.results if state is not None else None
        if results is not None:
            if results:
                st.success(f"Found {len(results)} matching projects")
                # Every card's score is relative to the best hit below, so the top
                # one always reads 100%. Say so here when none of them is actually
                # a relevant match, or the list looks like a perfect result.
                if state is not None and state.weak_match:
                    st.warning(
                        "No programme in this collection is a strong match for this "
                        "query. The results below are the closest available, not "
                        "necessarily relevant — the percentages compare them with "
                        "each other, not with what a good match would look like."
                    )
                watchlisted_ids = self._load_watchlisted_ids()
                for rank, result in enumerate(results, start=1):
                    self._render_result_with_watchlist(result, watchlisted_ids, rank)
                if self.source_attribution:
                    st.caption(self.source_attribution)
            else:
                st.warning(self.no_results_message)

    # ── Watchlist helpers ─────────────────────────────────────────────

    def _load_watchlisted_ids(self) -> set[str]:
        """Load the current user's watchlisted project IDs for this collection."""
        if not is_auth_enabled() or not is_authenticated():
            return set()
        user_id = st.session_state.get(SESSION_USER_ID)
        if user_id is None:
            return set()
        try:
            repo = get_watchlist_repository()
            return repo.get_watchlisted_ids(user_id, self.collection_type)
        except Exception:
            logger.debug("Failed to load watchlist", exc_info=True)
            return set()

    def _render_result_with_watchlist(
        self, result: dict[str, Any], watchlisted_ids: set[str],
        rank: int | None = None,
    ) -> None:
        """Render a result with an optional watchlist checkbox above it."""
        project_id = result.get("project_id", "")
        is_on_watchlist = project_id in watchlisted_ids

        if is_auth_enabled() and is_authenticated() and project_id:
            checkbox_key = f"wl_{self.collection_type}_{project_id}"
            label = "On Watchlist" if is_on_watchlist else "Add to Watchlist"
            checked = st.checkbox(label, value=is_on_watchlist, key=checkbox_key)

            if checked and not is_on_watchlist:
                self._add_to_watchlist(result)
                watchlisted_ids.add(project_id)
            elif not checked and is_on_watchlist:
                self._remove_from_watchlist(project_id)
                watchlisted_ids.discard(project_id)

        self.render_result(result, rank)

    def _add_to_watchlist(self, result: dict[str, Any]) -> None:
        user_id = st.session_state.get(SESSION_USER_ID)
        if user_id is None:
            return
        try:
            repo = get_watchlist_repository()
            repo.add(
                user_id=user_id,
                project_id=result.get("project_id", ""),
                collection_type=self.collection_type,
                project_title=result.get("project_title", ""),
                project_website=result.get("project_website", ""),
            )
        except Exception:
            logger.warning("Failed to add to watchlist", exc_info=True)

    def _remove_from_watchlist(self, project_id: str) -> None:
        user_id = st.session_state.get(SESSION_USER_ID)
        if user_id is None:
            return
        try:
            repo = get_watchlist_repository()
            repo.remove(user_id, project_id, self.collection_type)
        except Exception:
            logger.warning("Failed to remove from watchlist", exc_info=True)


class GermanFundingSearchPage(BaseFundingSearchPage):
    """Search page for the German federal funding database (`/v1/search/german`).

    Adds taxonomy-based sidebar multiselect filters fetched from `/v1/vocab/german`.
    Filters are sent server-side with each search request.
    """
    FIELD_CONFIG = [
        ("funding_location", "Funding location", "federal_locations"),
        ("funding_type", "Type of funding", "federal_funding_type"),
        ("eligible_applicants", "Eligible applicants", "federal_eligible"),
        ("funding_area", "Funding area", "federal_funding_area"),
    ]

    # The programme texts shown above are licensed CC BY-ND 4.0 with the BMWE as
    # rights holder, which requires attribution wherever they are republished. Every
    # row also carries its own attribution string in the `license_info` column.
    source_attribution = (
        "Source: [Förderdatenbank des Bundes](https://www.foerderdatenbank.de/) — "
        "© Bundesministerium für Wirtschaft und Energie, licensed "
        "[CC BY-ND 4.0](https://creativecommons.org/licenses/by-nd/4.0/deed.de). "
        "Data prepared by [CorrelAid e.V.](https://github.com/CorrelAid/fdb_scraper)."
    )

    @property
    def collection_type(self) -> str:
        """Return the collection identifier for watchlist scoping."""
        return "german"

    @property
    def search_endpoint(self) -> str:
        """Return the FastAPI endpoint path for German federal funding search."""
        return "/v1/search/german"

    @property
    def search_button_key(self) -> str:
        """Return the Streamlit widget key for the German search button."""
        return "search_federal"

    @property
    def query_key(self) -> str:
        """Return the Streamlit widget key for the German query text area."""
        return FEDERAL_QUERY_KEY

    @property
    def no_results_message(self) -> str:
        """Return the message shown when no German funding projects match the active filters."""
        return "No projects match your selected filters."

    def render_sidebar(self) -> tuple[float, int, dict[str, Any]]:
        """Render German-specific sidebar with taxonomy multiselects and search controls.

        Fetches the taxonomy artifact from ``/v1/vocab/german`` and builds
        multiselect widgets for each field in ``FIELD_CONFIG``. Falls back
        gracefully with a warning when the taxonomy is unavailable.

        Returns:
            tuple[float, int, dict[str, Any]]: ``(semantic_weight, search_limit,
                context)`` where *context* contains a ``filters`` dict of the
                selected taxonomy keys.
        """
        restore = self._consume_restore()

        options_by_field: dict[str, list[str]] = {}
        labels_by_field: dict[str, dict[str, str]] = {}
        taxonomy_columns: dict[str, Any] = {}
        taxonomy_error: Exception | None = None

        try:
            taxonomy = fetch_german_taxonomy(self.fastapi_url)
            raw_columns = taxonomy.get("columns", {})
            if isinstance(raw_columns, dict):
                taxonomy_columns = raw_columns
        except Exception as error:
            taxonomy_error = error
            taxonomy_columns = {}

        for field, _, _ in self.FIELD_CONFIG:
            entries = taxonomy_columns.get(field, []) if isinstance(taxonomy_columns, dict) else []
            options_by_field[field] = [entry.get("key", "") for entry in entries if entry.get("key")]
            labels_by_field[field] = {
                entry.get("key", ""): entry.get("canonical", entry.get("key", ""))
                for entry in entries
                if entry.get("key")
            }

        # Applied here rather than in _consume_restore because it needs the taxonomy
        # fetched just above: a saved value that is no longer in the vocabulary is
        # dropped, so a withdrawn taxonomy key cannot put the multiselect into a state
        # its options do not allow.
        if restore is not None and restore.filters:
            for field, _, widget_key in self.FIELD_CONFIG:
                raw = restore.filters.get(field, [])
                available = options_by_field.get(field, [])
                st.session_state[widget_key] = [v for v in raw if v in available]

        st.sidebar.header("Filter Options")
        selected_filters: dict[str, list[str]] = {}
        for field, label, widget_key in self.FIELD_CONFIG:
            selected_filters[field] = st.sidebar.multiselect(
                label,
                options_by_field.get(field, []),
                format_func=lambda key, f=field: labels_by_field.get(f, {}).get(key, key),
                key=widget_key,
            )

        if taxonomy_error is not None:
            logger.warning("Failed to fetch German taxonomy: %s", taxonomy_error)
            st.sidebar.warning("Filters are unavailable (taxonomy could not be loaded).")

        semantic_weight, search_limit = self._render_common_sidebar_controls()

        return float(semantic_weight), int(search_limit), {"filters": selected_filters}

    def render_result(self, result: dict[str, Any], rank: int | None = None) -> None:
        """Render a single German federal funding project as a Streamlit card.

        Args:
            result (dict[str, Any]): Project dict returned by the search backend.
            rank (int | None, default=None): 1-based position in the result list.
        """
        render_german_project_result(result, rank)


class EuFundingSearchPage(BaseFundingSearchPage):
    """Search page for EU funding calls (`/v1/search/eu`).

    Provides a minimal sidebar (search limit + semantic weight slider) with no
    taxonomy filters, as EU data uses a smaller controlled vocabulary.
    """

    @property
    def collection_type(self) -> str:
        """Return the collection identifier for watchlist scoping."""
        return "eu"

    @property
    def search_endpoint(self) -> str:
        """Return the FastAPI endpoint path for EU funding search."""
        return "/v1/search/eu"

    @property
    def search_button_key(self) -> str:
        """Return the Streamlit widget key for the EU search button."""
        return "search_eu"

    @property
    def query_key(self) -> str:
        """Return the Streamlit widget key for the EU query text area."""
        return EU_QUERY_KEY

    def render_sidebar(self) -> tuple[float, int, dict[str, Any]]:
        """Render EU-specific sidebar with search limit and semantic weight controls.

        Returns:
            tuple[float, int, dict[str, Any]]: ``(semantic_weight, search_limit,
                context)`` where *context* is an empty dict (no taxonomy filters
                for EU searches).
        """
        # No taxonomy filters on this page, so the shared controls are the whole job.
        self._consume_restore()

        semantic_weight, search_limit = self._render_common_sidebar_controls()

        return float(semantic_weight), int(search_limit), {}

    def render_result(self, result: dict[str, Any], rank: int | None = None) -> None:
        """Render a single EU funding call as a Streamlit card.

        Args:
            result (dict[str, Any]): Project dict returned by the search backend.
            rank (int | None, default=None): 1-based position in the result list.
        """
        render_eu_project_result(result, rank)
