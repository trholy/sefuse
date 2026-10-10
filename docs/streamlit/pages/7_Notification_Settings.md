# `streamlit.app_pages.7_Notification_Settings`

Entry-point script for the page where a user stores their Gotify application token.

Saved-search alerts always land in the in-app inbox on the Saved Searches page. When the operator has switched on Gotify push, a user who stores a token here also receives them on their device. The server address is set by the operator in `GOTIFY_URL`; users supply only their own token.

This module contains no function or class definitions. It runs top to bottom on every render.

---

## Access and visibility

| Step | Action |
|---|---|
| 1 | `require_page_access("Notification Settings", ...)` — runs the auth gate and returns the user's id. |
| 2 | If `gotify_push_enabled()` is false, the page explains that push notifications are disabled on this instance and stops. |

The sidebar link is hidden when push is off (see [Navigation](../ui/navigation.md)), so step 2 only matters when the page is reached directly. `gotify_push_enabled()` is also false when `ALERTS_ENABLED=false` or when the Gotify settings are misconfigured.

`shared.gotify` and `shared.gotify_config` are imported after that check, so a misconfigured deployment cannot break the page before it has explained itself.

---

## Page content

The page names the instance's Gotify server (`GotifyConfig.base_url`) and explains how to create an application token there. It then states whether a token is already configured for the account.

The token field is a password input and is always empty; a stored token is never displayed.

| Control | Action |
|---|---|
| **Save token** | Verifies the entered token with `verify_token(base_url, token)`, which sends a real test notification. On success the token is stored with `UserRepository.update_gotify_token(user_id, token)`, encrypted at rest (see [Secrets Box](../../shared/secrets_box.md)). On failure the reason is shown and nothing is stored. |
| **Send test notification** | Enabled when a token is stored. Sends a sample alert message through `GotifyClient(current_token).send(...)`. |
| **Remove token** | Enabled when a token is stored. Stores an empty token, which switches push off for this user. |
