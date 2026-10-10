import os

# ─── Ollama / embedding ───────────────────────────────────────────────────────

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = os.getenv("MODEL", "bge-m3")
TOKENIZER = os.getenv("TOKENIZER", "BAAI/bge-m3")
OLLAMA_EMBED_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_EMBED_TIMEOUT_SECONDS", "120"))

# ─── Vector schema ────────────────────────────────────────────────────────────

VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", "1024"))

# ─── Saved-search alert guards ────────────────────────────────────────────────

# A run that stamps more than max(MIN, RATIO × active programmes) as first seen in a
# collection that was already tracked is treated as upstream ids changing, and the
# programmes are stamped as legacy instead of alerting.
FIRST_SEEN_BURST_MIN = int(os.getenv("FIRST_SEEN_BURST_MIN", "25"))
FIRST_SEEN_BURST_RATIO = float(os.getenv("FIRST_SEEN_BURST_RATIO", "0.1"))

# A new programme at least this similar (dense cosine of its first chunk) to an
# existing one is recorded as a near-duplicate and never alerts as new.
DUPLICATE_COSINE = float(os.getenv("DUPLICATE_COSINE", "0.97"))

# ─── Payload field constants ──────────────────────────────────────────────────

# Fields kept out of the Qdrant payload. `description` is the text being embedded, so
# storing it again per chunk is pure duplication; `legal_basis` is the full legal
# Richtlinie — never returned by the API or shown in the UI, and by far the largest
# column, duplicated into every chunk of a project.
PAYLOAD_EXCLUDE_FIELDS: frozenset[str] = frozenset({"description", "legal_basis"})

PAYLOAD_INDEX_FIELDS: tuple[str, ...] = (
    "project_uuid",
    "funding_type_keys",
    "funding_area_keys",
    "funding_location_keys",
    "eligible_applicants_keys",
)

# Payload keys the search API actually returns, and therefore the input to the
# `payload_hash` that decides whether an indexed project needs its payload refreshed.
#
# Must stay in step with the keys `_aggregate_results` reads in `main.py` — a field
# added there but not here would never trigger a refresh, so the API would keep
# serving the value captured when the project was last embedded. A test asserts the
# two agree.
#
# Deliberately not the whole payload: `id_hash`, `more_info`, `funding_body`,
# `further_links`, `license_info` and friends are never returned, so hashing them
# would trigger refreshes nobody can observe.
PAYLOAD_DISPLAY_FIELDS: tuple[str, ...] = (
    "title",
    "url",
    "project_short_description",
    "project_full_description",
    "topic_destination",
    "date_1",
    "date_2",
    "funding_type",
    "funding_area",
    "funding_location",
    "eligible_applicants",
    "funding_type_keys",
    "funding_area_keys",
    "funding_location_keys",
    "eligible_applicants_keys",
    "status_note",
    "deadlines",
    "keywords_extracted",
    "contact_info_institution",
)

# Fields of PAYLOAD_DISPLAY_FIELDS whose absent value normalises to [] rather than "".
# The distinction matters because the two collections carry different subsets: EU has
# no `status_note`/`keywords_extracted` and only one `*_keys` field, German has no
# dates. Normalising exactly as `_aggregate_results` does is what keeps a hash
# comparable across both pipelines.
PAYLOAD_LIST_FIELDS: frozenset[str] = frozenset({
    "funding_type",
    "funding_area",
    "funding_location",
    "eligible_applicants",
    "funding_type_keys",
    "funding_area_keys",
    "funding_location_keys",
    "eligible_applicants_keys",
    "keywords_extracted",
})
