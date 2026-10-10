# `streamlit.app_pages.5_Saved_Searches`

Entry-point script for the page that holds a user's alert inbox and their saved searches.

A search is saved from a search page through the **Save Search** dialog (see [Search Pages](../ui/search_pages.md)). This page lists the saved searches, restores or deletes them, and configures their alerts. How an alert decides that a new programme matches is described in [Saved-Search Alerts](../../fastapi/alerts.md).

This module contains no function or class definitions. It runs top to bottom on every render.

---

## Access

`require_page_access("Saved Searches", ...)` runs the auth gate and returns the user's id. With `AUTH_ENABLED=false` the page explains that saved searches require authentication and stops.

---

## Alert Matches

Rendered above the saved searches, and only when `alerts_enabled()` is true.

The section is always shown, including when it is empty, so the feature is visible before any alert has fired. It lists the user's 50 most recent matches, read and unread, from `NotificationRepository.get_recent(user_id)`.

| Control | Action |
|---|---|
| **Mark all as read (n)** | Shown when there are unread matches. Calls `mark_all_read(user_id)`. |
| **Clear all** | Calls `delete_all(user_id)`. |
| **Read** (per match) | Shown on unread matches. Calls `mark_read(id, user_id)`. |
| **Delete** (per match) | Calls `delete(id, user_id)`. |

Each match shows its title, linked to the programme's website when one is stored, the time it was found, and a **NEW** marker while unread. No score is shown: the stored value is a raw cosine, which is not on the same scale as the percentage the search pages display.

---

## Saved Searches

Each saved search is an expander titled with its name and collection (`GERMAN` or `EU`). It shows the query, semantic weight, result limit, any taxonomy filters, and the creation time.

| Control | Action |
|---|---|
| **Restore** | Writes a `RestorePayload` (filters, semantic weight, limit) under `RESTORE_KEY`, puts the query text into the target page's query key, and switches to the Federal or EU search page. The target page consumes the payload once. |
| **Delete** | Calls `SavedSearchRepository.delete(search_id, user_id)` and reruns. |

With no saved searches, the page shows an info message and stops.

---

## Alert Settings

Rendered inside each saved search's expander, and only when `alerts_enabled()` is true.

| Control | Description |
|---|---|
| **Enable alerts** | Checkbox, initialised from `alert_enabled`. |
| Match level | `render_alert_level_slider` — Broad, Balanced or Strict. |
| **Save Alert Config** | Calls `SavedSearchRepository.update_alert_config(...)`. Switching an alert on from off restarts its baseline, so only programmes indexed from then on count as new. |

When an alert is enabled but the user has no working push channel, a caption points to the Notification Settings page. The time of the last alert check is shown once the alert has run.

---

## Behaviour with `ALERTS_ENABLED=false`

The Alert Matches section and every Alert Settings block are skipped. The saved searches themselves stay listed, and Restore and Delete keep working.
