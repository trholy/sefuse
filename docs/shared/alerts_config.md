# `shared.alerts_config`

Deployment-wide master switch for saved-search alerts, read by both FastAPI and Streamlit.

`ALERTS_ENABLED` sits above `GOTIFY_ENABLED`. `GOTIFY_ENABLED=false` turns off push delivery while alerts keep running; `ALERTS_ENABLED=false` turns off the whole feature: the nightly check job, the in-app inbox, the sidebar badge and every alert control in the UI. Saved searches themselves keep working.

Nothing here can be misconfigured: an unset variable reads as on, and an unrecognised value reads as off instead of raising.

See [Saved-Search Alerts](../fastapi/alerts.md) for what the switch disables in each service.

---

## Functions

### `alerts_enabled() -> bool`

Return whether saved-search alerts are switched on for this deployment.

**Returns:** `bool` — `True` when `ALERTS_ENABLED` is unset or truthy (`1`, `true`, `yes`, `on`, case-insensitive); `False` for any other value.

The result is cached with `lru_cache`, so the environment is read once per process.
