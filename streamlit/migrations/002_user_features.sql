-- Session persistence
CREATE TABLE IF NOT EXISTS auth_sessions (
    token       VARCHAR(128) PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_auth_sessions_user_id ON auth_sessions (user_id);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_expires_at ON auth_sessions (expires_at);

-- Watchlist
CREATE TABLE IF NOT EXISTS user_watchlist (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    project_id      VARCHAR(128) NOT NULL,
    collection_type VARCHAR(16) NOT NULL CHECK (collection_type IN ('german', 'eu')),
    project_title   TEXT NOT NULL DEFAULT '',
    project_website TEXT NOT NULL DEFAULT '',
    added_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, project_id, collection_type)
);

CREATE INDEX IF NOT EXISTS ix_user_watchlist_user_id ON user_watchlist (user_id);

-- Saved searches with alert configuration
CREATE TABLE IF NOT EXISTS saved_searches (
    id                      BIGSERIAL PRIMARY KEY,
    user_id                 BIGINT NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    title                   VARCHAR(128) NOT NULL,
    query_text              TEXT NOT NULL,
    collection_type         VARCHAR(16) NOT NULL CHECK (collection_type IN ('german', 'eu')),
    filters                 JSONB NOT NULL DEFAULT '{}',
    semantic_weight         REAL NOT NULL DEFAULT 0.7,
    search_limit            INTEGER NOT NULL DEFAULT 20,
    alert_enabled           BOOLEAN NOT NULL DEFAULT FALSE,
    alert_threshold         REAL NOT NULL DEFAULT 0.8,
    alert_apprise_urls      TEXT[] NOT NULL DEFAULT '{}',
    alert_last_run          TIMESTAMPTZ,
    alert_known_project_ids TEXT[] NOT NULL DEFAULT '{}',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_saved_searches_user_id ON saved_searches (user_id);
CREATE INDEX IF NOT EXISTS ix_saved_searches_alert_enabled
    ON saved_searches (alert_enabled) WHERE alert_enabled = TRUE;

-- In-app alert notifications
CREATE TABLE IF NOT EXISTS alert_notifications (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    saved_search_id BIGINT NOT NULL REFERENCES saved_searches(id) ON DELETE CASCADE,
    project_id      VARCHAR(128) NOT NULL,
    project_title   TEXT NOT NULL DEFAULT '',
    project_website TEXT NOT NULL DEFAULT '',
    matching_score  REAL NOT NULL DEFAULT 0,
    is_read         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_alert_notifications_user_unread
    ON alert_notifications (user_id, is_read) WHERE is_read = FALSE;
