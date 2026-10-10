-- Replace the relative score threshold with three named match levels.
--
-- The old ``alert_threshold`` was compared with a score divided by the best hit of
-- each search, so the top result was always 1.0 and the threshold only ever meant
-- "within X% of the best result" — it said nothing about whether a programme was
-- actually relevant.
--
-- A saved search now stores a level *name* (broad / balanced / strict) and FastAPI
-- decides what it means at alert time, relative to the saved query: would this
-- programme rank among the query's top k existing programmes, and does it score above
-- what deliberately off-topic queries reach in that collection. Nothing about the rule
-- is stored, because a raw cosine is not comparable across queries — short queries
-- score lower against everything — so there is no useful number to keep.
--
-- Note for anyone reading the history: this file originally also created a
-- ``match_calibration`` table holding absolute per-collection cosine floors,
-- recomputed daily from a sample of programmes. Those floors turned out to be biased
-- by query length and collection density, and 007 dropped the table again. Both
-- migrations only ever existed on an unmerged branch, so the table is simply never
-- created rather than created and dropped — nothing deployed has to replay a model
-- that did not survive its own branch. 007's surviving change (``duplicate_of``) is
-- folded in at the bottom.

ALTER TABLE saved_searches
    ADD COLUMN IF NOT EXISTS alert_level TEXT NOT NULL DEFAULT 'balanced'
    CHECK (alert_level IN ('broad', 'balanced', 'strict'));

-- Carry each existing alert's intent over before the old column goes: a high
-- relative threshold meant "only near the best result", a low one "most results".
-- Guarded so the file stays safe to run against a database that already dropped it.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'saved_searches'
          AND column_name = 'alert_threshold'
    ) THEN
        UPDATE saved_searches
        SET alert_level = CASE
            WHEN alert_threshold >= 0.9 THEN 'strict'
            WHEN alert_threshold >= 0.7 THEN 'balanced'
            ELSE 'broad'
        END;
        ALTER TABLE saved_searches DROP COLUMN alert_threshold;
    END IF;
END $$;

-- Dropped defensively rather than assumed absent: a database that applied the
-- original 006 has the table, and this file is recorded as applied there, so it will
-- not run again — but a database that applied 006 and *not* 007 would otherwise keep
-- it forever.
DROP TABLE IF EXISTS match_calibration;

-- A new programme that is a near-copy of an older one (a state variant, a successor
-- re-published under a new id) points at it here and does not alert as new. Folded in
-- from 007; ``fetch_new_since`` excludes rows where this is set.
ALTER TABLE programme_first_seen
    ADD COLUMN IF NOT EXISTS duplicate_of TEXT NULL;
