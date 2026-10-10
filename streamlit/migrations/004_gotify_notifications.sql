-- Replace Apprise notification targets with per-user Gotify app tokens.
--
-- SeFuSe pushes through one central, operator-run Gotify server (GOTIFY_URL),
-- so no server address is stored per user — only the user's application token,
-- which is their private channel on that server. The token is held as Fernet
-- ciphertext (see shared/secrets_box.py), never as plaintext.

ALTER TABLE auth_users
    ADD COLUMN IF NOT EXISTS gotify_token TEXT NOT NULL DEFAULT '';

ALTER TABLE saved_searches
    DROP COLUMN IF EXISTS alert_apprise_urls;

-- Supports the nightly retention sweep that prunes alert_notifications older
-- than ALERT_NOTIFICATION_RETENTION_DAYS.
CREATE INDEX IF NOT EXISTS ix_alert_notifications_created_at
    ON alert_notifications (created_at);
