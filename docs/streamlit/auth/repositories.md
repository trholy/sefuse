# Streamlit auth repositories

PostgreSQL-backed repositories for sessions, saved searches, the watchlist and alert notifications. Each lives in its own module under `streamlit/src/auth/` and extends `BaseRepository`.

| Module | Class | Table |
|---|---|---|
| `auth.base_repository` | `BaseRepository` | — |
| `auth.session_repository` | `SessionRepository` | `auth_sessions` |
| `auth.saved_search_repository` | `SavedSearchRepository` | `saved_searches` |
| `auth.watchlist_repository` | `WatchlistRepository` | `user_watchlist` |
| `auth.notification_repository` | `NotificationRepository` | `alert_notifications` |

The tables are created by the migrations in `streamlit/migrations/` (see [Migrate](migrate.md)). Every method that reads or changes a user's rows takes the `user_id` and scopes its query to it.

---

## `BaseRepository`

Common infrastructure for the repositories.

**Parameters:**

- `database` (`Database`): Connection pool factory used for all queries.

### `_execute(query, params=None, *, fetch=False, fetchone=False)`

Open a connection from the pool, run a parameterised query and commit on success.

**Returns:** `list[dict]` when `fetch` is set, `dict | None` when `fetchone` is set, `None` for write queries.

---

## `SessionRepository`

Manages the session tokens behind the cross-tab session cookie (see [Cookies](cookies.md)). Tokens are random 64-character hex strings stored with an expiry timestamp.

| Method | Description |
|---|---|
| `create_session(user_id, timeout_minutes) -> str` | Create a session and return its token. |
| `validate_and_refresh(token, timeout_minutes) -> dict \| None` | Validate a token and extend its expiry (sliding window). Returns `user_id`, `username` and `role`, or `None` if the token is invalid or expired or the user is inactive. |
| `delete_session(token) -> None` | Delete one session (logout). |
| `delete_user_sessions(user_id) -> None` | Delete all sessions of a user. |
| `cleanup_expired() -> None` | Delete all expired sessions. |

Expired sessions fail validation whether or not they have been deleted. FastAPI removes them once a day at 02:00.

---

## `SavedSearchRepository`

CRUD operations on saved searches.

### `SavedSearch`

Dataclass for one saved search.

| Field | Type | Description |
|---|---|---|
| `id`, `user_id` | `int` | Row id and owner. |
| `title` | `str` | Name given by the user. |
| `query_text` | `str` | The saved query. |
| `collection_type` | `str` | `"german"` or `"eu"`. |
| `filters` | `dict` | Saved taxonomy filters. |
| `semantic_weight` | `float` | Saved semantic weight. |
| `search_limit` | `int` | Saved result limit. |
| `alert_enabled` | `bool` | Whether the alert is on. |
| `alert_level` | `str` | `"broad"`, `"balanced"` or `"strict"`. |
| `alert_last_run` | `datetime \| None` | Time of the last alert check. |
| `alert_known_project_ids` | `list[str]` | Programmes this alert has already announced. |
| `alert_baseline_at` | `datetime \| None` | Only programmes first indexed after this time count as new. |
| `created_at`, `updated_at` | `datetime` | Timestamps. |

### Methods

| Method | Description |
|---|---|
| `create(user_id, title, query_text, collection_type, filters, semantic_weight, search_limit) -> int` | Create a saved search and return its id. |
| `find_duplicate(user_id, query_text, collection_type, filters, semantic_weight) -> SavedSearch \| None` | Return the user's existing saved search with the same query, collection, filters and semantic weight. Title and result limit are not compared. |
| `list_by_user(user_id) -> list[SavedSearch]` | All saved searches of a user, newest first. |
| `get_by_id(search_id, user_id) -> SavedSearch \| None` | One saved search. |
| `delete(search_id, user_id) -> None` | Delete a saved search. |
| `update_alert_config(search_id, user_id, alert_enabled, alert_level) -> None` | Update the alert settings. Raises `ValueError` for an unknown level. |

The save dialog calls `find_duplicate` before `create`, because two identical saved searches would announce every match twice. This is an application-level check and not a database constraint, so two saves racing each other can both succeed.

`update_alert_config` sets `alert_baseline_at` to the current time when an alert is switched from off to on. Saving the settings again while the alert is already on leaves the baseline unchanged.

---

## `WatchlistRepository`

CRUD operations on the per-user watchlist.

### `WatchlistItem`

Dataclass for one watchlisted programme: `id`, `user_id`, `project_id`, `collection_type`, `project_title`, `project_website`, `added_at`.

### Methods

| Method | Description |
|---|---|
| `get_watchlisted_ids(user_id, collection_type) -> set[str]` | Project ids the user has watchlisted in one collection. |
| `add(user_id, project_id, collection_type, project_title, project_website) -> None` | Add a programme. No-op if it is already on the watchlist. |
| `remove(user_id, project_id, collection_type) -> None` | Remove a programme. |
| `list_items(user_id) -> list[WatchlistItem]` | All watchlisted programmes, newest first. |
| `list_items_by_collection(user_id, collection_type) -> list[WatchlistItem]` | Watchlisted programmes of one collection. |

---

## `NotificationRepository`

CRUD operations on the in-app alert inbox. The rows are written by FastAPI's alert job (see [Saved-Search Alerts](../../fastapi/alerts.md)); Streamlit reads them, marks them read and deletes them.

### `AlertNotification`

Dataclass for one alert match: `id`, `user_id`, `saved_search_id`, `project_id`, `project_title`, `project_website`, `matching_score`, `is_read`, `created_at`.

`matching_score` holds a raw cosine similarity and is kept for diagnostics. The UI does not display it.

### Methods

| Method | Description |
|---|---|
| `get_unread_count(user_id) -> int` | Number of unread matches; backs the sidebar badge. |
| `get_unread(user_id) -> list[AlertNotification]` | Unread matches, newest first. |
| `get_recent(user_id, limit=50) -> list[AlertNotification]` | Recent matches, read and unread, newest first. |
| `mark_read(notification_id, user_id) -> None` | Mark one match as read. |
| `mark_all_read(user_id) -> None` | Mark all unread matches as read. |
| `delete(notification_id, user_id) -> None` | Delete one match. |
| `delete_all(user_id) -> None` | Delete every match of a user. |

FastAPI prunes matches older than `ALERT_NOTIFICATION_RETENTION_DAYS` (default 30) once a day.
