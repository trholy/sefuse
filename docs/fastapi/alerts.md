# Saved-Search Alerts

How a saved search turns into a notification: which programmes are even considered,
how "good enough" is decided, and what stops false alerts.

Modules: `fastapi/src/utils/first_seen.py`, `fastapi/src/utils/match_levels.py`,
`fastapi/src/utils/alert_service.py`, the scoring helpers in
`fastapi/src/utils/search_service.py`, and `main._alert_score_fn`, which binds them to
the module-level Qdrant managers.
Schema: migrations `005_alert_first_seen.sql`, `006_alert_levels.sql`,
`008_first_seen_index.sql`.

---

## The run, end to end

Once a day at `ALERT_CHECK_HOUR`, for every saved search with `alert_enabled = TRUE`:

1. **Candidates** — `first_seen.fetch_new_since(collection_type, alert_baseline_at)`
   returns the programmes first seen after the alert was switched on that are not
   marked as near-duplicates. Anything already in `alert_known_project_ids` is
   dropped. **With no candidates the run stops here**, without embedding the query.
2. **Scoring** — `main._alert_score_fn` embeds the saved query once and scores only
   those candidates, exactly (non-HNSW), one best chunk per programme.
3. **Filters** — the saved taxonomy filters and drop-N/A are applied through the same
   `apply_result_filters` interactive search uses.
4. **Judging** — each survivor is judged by `match_levels.judge` against the saved
   level (see below).
5. **Delivery** — passing matches go to the in-app inbox and, if the user has a
   Gotify token, to their device; ids of successful notifications are appended to
   `alert_known_project_ids`.

!!! note "Why not just re-run the search"
    The obvious implementation — re-run the saved search and look at its top
    `search_limit` results — silently misses a new programme that older ones outrank.
    Scoring the new programmes directly is the prospective-search ("percolation")
    shape: few documents, many standing queries.

---

## What counts as new

`programme_first_seen(collection_type, project_id, first_seen_at, duplicate_of)` is
written by the embedding pipeline (`Pipeline._record_first_seen`), not by the alert
job. It lives in Postgres rather than a Qdrant payload because a re-embed deletes and
re-inserts a programme's points, which would lose a payload stamp.

- A programme not yet indexed is stamped `NOW()`; one already indexed but unstamped
  gets the epoch, so nothing that predates tracking can alert.
- Rows are never overwritten, so a programme that leaves the index and returns keeps
  its original time.
- `saved_searches.alert_baseline_at` is set to `NOW()` when an alert is switched on
  (off → on only), so enabling an alert never replays history.
- Every function fails soft: a Postgres outage costs an alert, never causes a false
  one, because a programme with no row is not new.

### Guards against false "new" programmes

| Guard | What it catches | Behaviour |
|---|---|---|
| **Re-key burst** (`FIRST_SEEN_BURST_MIN`, `FIRST_SEEN_BURST_RATIO`) | Upstream ids changing, which makes the whole index look new | More than `max(25, 10% of active)` new programmes in an already-tracked collection → all stamped as legacy, error logged |
| **Near-duplicate** (`DUPLICATE_COSINE`) | A state variant or a successor re-published under a new id | First chunk within 0.97 cosine of an older programme → `duplicate_of` set, excluded from candidates |

---

## Match levels

A saved search stores a level *name* (`broad` / `balanced` / `strict`,
`shared/alert_levels.py`). The rule behind the name is **not** a fixed cosine: raw
`bge-m3` cosines are not comparable across queries, because a short query scores lower
against everything. Two conditions must hold.

| Level | Rank: among the query's top *k* **existing** programmes | Noise floor |
|---|---|---|
| Broad | 25 | best canary cosine + `ALERT_NOISE_MARGIN` |
| Balanced | 10 | same |
| Strict | 3 | same |

- **Rank** absorbs the query-length shift — a short query's rank-*k* cosine is lower
  too — and is what the UI labels describe ("top 25 / 10 / 3"). Candidates are
  excluded from the ranking, so new programmes are measured against existing ones and
  not against each other.
- **Noise floor** is per collection: the best cosine any `CANARIES` query (off-topic,
  short and long, in the collection's language) reaches in that collection, plus
  `ALERT_NOISE_MARGIN` (default `0.04`). It is what stops a vague or off-topic saved
  search from alerting simply because *something* always ranks first. `main._noise_floor`
  measures it once per collection and caches it until the next embedding run.
- `ALERT_LEVEL_RULES` (JSON `{"level": k}`) overrides the ranks; an invalid value is
  logged and ignored.

!!! warning "A z-score does not work here"
    Judging "stands out from the query's own score distribution" was tried first and
    fails: the best of ~2,500 programmes is always 3–5 standard deviations above the
    mean, relevant or not. Measured on the live index, every off-topic canary passed,
    and the on-topic query "energy" (z 3.5) looked *less* distinctive than
    "Käsekuchen" (z 4.6).

!!! warning "Canaries must have no funding counterpart"
    Holiday and tourism canaries matched real *Familienferienreisen* programmes at
    0.52 and inflated the German floor. Anything that hits a genuine programme
    belongs nowhere in that list.

### Consequences worth knowing

- A one- or two-word query may have **no** programme above the floor — it can then
  never alert. Nothing in the UI says so yet.
- For such a vague query the levels differ less than their labels suggest, because the
  floor, not the rank, is the binding condition.

---

## Operating it

The alert check runs once a day at `ALERT_CHECK_HOUR`; there is no HTTP endpoint to
trigger it by hand. With `LOG_LEVEL=DEBUG` the run logs each candidate's cosine, rank
and the collection's floor.

Measured on the live index (September 2026): German floor `0.536`, EU floor `0.517`.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `ALERTS_ENABLED` | `true` | Master switch. `false` switches the feature off entirely and makes every other row here irrelevant — see below. |
| `ALERT_CHECK_HOUR` | `5` | Hour (UTC) of the daily alert check. |
| `ALERT_NOTIFICATION_RETENTION_DAYS` | `30` | Age at which the nightly sweep prunes the in-app inbox (runs at `ALERT_CHECK_HOUR + 1`). |
| `ALERT_LEVEL_RULES` | — | Optional JSON `{"level": k}` overriding the rank per level. |
| `ALERT_NOISE_MARGIN` | `0.04` | How far above the best canary cosine a candidate must score. |
| `FIRST_SEEN_BURST_MIN` / `FIRST_SEEN_BURST_RATIO` | `25` / `0.1` | Re-key burst guard. |
| `DUPLICATE_COSINE` | `0.97` | Near-duplicate threshold. |
| `GOTIFY_*` | — | Push delivery; see [Gotify Config](../shared/gotify_config.md). |

---

## Switching the feature off

`ALERTS_ENABLED=false` turns off saved-search alerts everywhere. It is read by both
services through `shared/alerts_config.py` (default on, so an existing deployment that
never sets it is unaffected), and it sits above `GOTIFY_ENABLED` — off here forces push
off too.

FastAPI:

- `alert_check_job` and `alert_notification_cleanup_job` are never scheduled. The five
  other jobs — both data-processing, both embedding, and the session cleanup — are
  untouched.
- The Gotify startup validation and reachability probe are skipped rather than ignored,
  so a stale `GOTIFY_URL` left in `.env` cannot abort startup of a deployment that does
  not use alerts.
- `AlertService.check_all_alerts` returns 0 without opening a connection.

Streamlit: the Notification Settings page disappears from the navigation, the sidebar
unread badge goes, and the Saved Searches page and the save-search dialog drop their
alert blocks. The Saved Searches page itself stays — restoring and deleting a saved
search has nothing to do with being notified about it.

Two things deliberately keep running, so the switch is reversible rather than
destructive:

- **First-seen stamping.** `Pipeline._record_first_seen` and `_mark_duplicates` still
  populate `programme_first_seen` on every embedding run. It is cheap, and it is the
  only history that makes switching alerts back on meaningful — without it, every
  programme indexed while alerts were off would look pre-existing forever.
- **Migrations.** `streamlit/migrations/` runs in full at startup regardless, so
  `saved_searches.alert_*`, `alert_notifications` and `programme_first_seen` survive.
