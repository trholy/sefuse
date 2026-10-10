-- Make saved-search alerts fire only for programmes that are genuinely new.
--
-- programme_first_seen records, per programme, when it first entered the index.
-- It lives in Postgres rather than in the Qdrant payload because a re-embed
-- deletes and re-inserts a programme's points, and a programme can drop out of
-- the index for a while (an EU call that closes and reopens, an upstream hiccup
-- under the truncation guard). A payload stamp would be lost each time and make
-- an old programme look new; this row survives both.
--
-- Programmes already indexed when the embedding pipeline first runs after this
-- migration are stamped with the epoch (1970-01-01), which is older than any
-- alert baseline, so they never count as new.
CREATE TABLE IF NOT EXISTS programme_first_seen (
    collection_type TEXT        NOT NULL CHECK (collection_type IN ('german', 'eu')),
    project_id      TEXT        NOT NULL,
    first_seen_at   TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (collection_type, project_id)
);

-- A match is "new" only if its programme was first seen after this moment.
-- Existing rows get the migration time, so alerts that are already enabled do not
-- replay history; the app moves it to NOW() whenever an alert is switched on.
ALTER TABLE saved_searches
    ADD COLUMN IF NOT EXISTS alert_baseline_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
