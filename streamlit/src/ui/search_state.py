"""The session-state objects the search pages keep between reruns.

Streamlit re-executes a page script on every interaction, so anything that must
outlive a click lives in ``st.session_state``. Two families of it:

**Cached search state** (`SearchState`) — one entry per page, under that page's
``results_key``. It used to be five separate keys built by appending ``""``,
``"_query"``, ``"_context"``, ``"_weight"`` and ``"_limit"`` to that prefix at four
different call sites. Adding a sixth piece of state meant finding all of them, and a
mistyped suffix silently desynced what was cached from what was displayed, with no
error.

**A one-shot restore payload** (`RestorePayload`) — written by the Saved Searches page
immediately before ``st.switch_page``, consumed once by whichever search page runs
next. This was three loose, un-namespaced keys, and they were popped *asymmetrically*:
the German page popped all three, the EU page only two, so restoring a German search
and then visiting the EU page left ``_restore_filters`` behind in session state
indefinitely. One key, popped in one shared place, cannot drift that way.

The query-box keys are named here too, because the Saved Searches page writes the
query straight into the target page's text-area key and had the literal strings
duplicated.
"""

from dataclasses import dataclass, field
from typing import Any

#: Session-state key for the one-shot restore payload. Un-namespaced on purpose: it is
#: handed from one page to another, so it cannot hang off either page's prefix.
RESTORE_KEY = "_restore_search"

#: Text-area keys for the two search pages. The Saved Searches page writes the restored
#: query directly into one of these, so both sides have to agree on the string.
FEDERAL_QUERY_KEY = "federal_query"
EU_QUERY_KEY = "eu_query"


@dataclass
class SearchState:
    """A completed search, cached so a rerun or a page switch does not lose it.

    Attributes:
        results (list[dict[str, Any]]): What the backend returned. An empty list is
            meaningful — it says the search ran and matched nothing, which is why the
            page tests for the *state* being present rather than for truthy results.
        query (str): The query text that produced these results, so returning to the
            page can put it back in the text area.
        context (dict[str, Any]): The sidebar context at search time, carrying a
            ``filters`` dict for the German page and empty for the EU page.
        weight (float): The semantic weight used.
        limit (int): The result limit used.
        weak_match (bool): The backend found nothing genuinely relevant for this
            query. Cached with the results rather than recomputed, because a rerun
            re-renders from this state without calling the backend again — and
            because each result's score is relative to the best hit, so without this
            flag a rerun would redisplay an off-topic search as a 100% match.
    """

    results: list[dict[str, Any]]
    query: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    weight: float = 0.7
    limit: int = 20
    weak_match: bool = False

    @property
    def filters(self) -> dict[str, Any]:
        """The taxonomy filters from `context`, or an empty dict."""
        return self.context.get("filters", {}) or {}


@dataclass
class RestorePayload:
    """Sidebar controls to reinstate when a saved search is restored.

    Every field is optional because the EU page has no taxonomy filters, and because
    the payload is applied before the widgets are drawn — a ``None`` means "leave that
    control alone" rather than "reset it".

    Attributes:
        filters (dict[str, Any] | None): Saved taxonomy selections, German only.
        semantic_weight (float | None): Saved blend weight.
        limit (int | None): Saved result limit.
    """

    filters: dict[str, Any] | None = None
    semantic_weight: float | None = None
    limit: int | None = None
