-- Index the lookup the alert run makes once per active alert, every night.
--
-- programme_first_seen was created in 005 with only its primary key
-- (collection_type, project_id). But nothing looks a programme up by id here — the
-- query that matters is first_seen.fetch_new_since:
--
--   SELECT project_id FROM programme_first_seen
--    WHERE collection_type = ? AND first_seen_at > ? AND duplicate_of IS NULL
--    ORDER BY first_seen_at, project_id
--
-- The primary key cannot serve that: first_seen_at is not in it, so Postgres reads
-- the whole table and sorts it. Measured on a 2 843-row table returning 4 matches,
-- that was a sequential scan discarding 2 839 rows — per alert, per cron cycle, on a
-- table that only ever grows, because nothing deletes from it.
--
-- Partial on `duplicate_of IS NULL` because that is the only side the query wants:
-- near-duplicates are excluded so they cannot alert as new, and they are dead weight
-- in this index. project_id is included so the index can answer the query on its own
-- without visiting the heap.
--
-- Every other table added in 002/004 got its supporting indexes; this one was missed.
CREATE INDEX IF NOT EXISTS ix_programme_first_seen_new
    ON programme_first_seen (collection_type, first_seen_at, project_id)
    WHERE duplicate_of IS NULL;
