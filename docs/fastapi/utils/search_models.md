# `fastapi.utils.search_models`

The request and response models for the search API. Pydantic validates these before a
route handler runs, so a malformed request is rejected with a 422 without reaching the
search path.

Both collections are served through one `SearchMatch`: the German and EU payloads do
not carry the same keys, so the fields only one of them has are defaulted rather than
split into two models. `utils/config.py` holds the matching `PAYLOAD_DISPLAY_FIELDS`,
and a test asserts the two agree in both directions — a field added here but not there
would never trigger a payload refresh.

Split out of `main.py`, together with `utils/search_service.py`.

---

### Class `SearchFilters`

Optional taxonomy filters applied server-side before returning search results. Each list field is matched with OR within the field, AND across fields. All list elements exceeding 64 characters are silently dropped; lists are capped at 50 items.

**Fields:**

- `funding_type` (`list[str] | None`, default `None`): Funding type taxonomy keys to filter on (e.g. `["Zuschuss"]`).
- `funding_area` (`list[str] | None`, default `None`): Funding area taxonomy keys.
- `funding_location` (`list[str] | None`, default `None`): Funding location taxonomy keys.
- `eligible_applicants` (`list[str] | None`, default `None`): Eligible applicant taxonomy keys.
- `drop_na` (`bool`, default `False`): When `True`, exclude results where both short and full description are `"N/A"`.

---

### Class `SearchMessage`

A single chat-style message carrying the user's search query.

**Fields:**

- `role` (`Literal["user"]`, default `"user"`): Message role; only `"user"` is accepted.
- `content` (`str`, min_length=1, max_length=5000): Search query text.

---

### Class `SearchRequest`

Validated request body for all search endpoints. FastAPI automatically rejects violations with HTTP 422 before the route handler is called.

**Fields:**

- `messages` (`list[SearchMessage]`, min_length=1, max_length=8): Conversation messages; the first item's `content` is used as the query.
- `model` (`str`): Ollama model name for query embedding, e.g. `"bge-m3"`.
- `limit` (`int`, ge=1, le=100, default=`20`): Maximum results to return.
- `semantic_weight` (`float`, ge=0.0, le=1.0, default=`0.7`): Hybrid search weight (0 = pure keyword, 1 = pure semantic).
- `filters` (`SearchFilters`, default=`SearchFilters()`): Optional taxonomy filters.

---

### Class `SearchMatch`

One aggregated project result. Scores are normalised to `[0, 1]` relative to the top result.

**Fields:**

- `project_id` (`str`): UUID of the funding project.
- `project_title` (`str`): Human-readable project title.
- `project_short_description` (`str`): Short summary.
- `project_full_description` (`str`): Full description text.
- `date_1` (`str`): First relevant date string (e.g. application deadline). EU only — the German pipeline carries no date columns, so this is `""` for German results.
- `date_2` (`str`): Second relevant date string (e.g. last-updated date).
- `funding_type` (`list[str]`): Human-readable funding type labels.
- `funding_area` (`list[str]`): Human-readable funding area labels.
- `funding_location` (`list[str]`): Human-readable funding location labels.
- `eligible_applicants` (`list[str]`): Human-readable eligible applicant labels.
- `funding_type_keys` (`list[str]`): Normalised taxonomy keys for `funding_type`.
- `funding_area_keys` (`list[str]`): Normalised taxonomy keys for `funding_area`.
- `funding_location_keys` (`list[str]`): Normalised taxonomy keys for `funding_location`.
- `eligible_applicants_keys` (`list[str]`): Normalised taxonomy keys for `eligible_applicants`.
- `project_website` (`str`): URL of the funding program's detail page.
- `relative_score` (`float`): Rank signal in `[0, 1]`, normalised against the top result **in this response**, after filtering. The best match always scores `1.0` however poor it is in absolute terms, and scores are not comparable between two responses. `SearchResponse.weak_match` is the absolute companion to it.

German-only fields, sourced from the published Förderdatenbank CSV. All default to `""` because both collections share this one response model and EU payloads carry no such keys:

- `status_note` (`str`): Editorial status banner, e.g. *"Programm aktiv, Antragstellung nicht möglich"*.
- `deadlines` (`str`): Application deadline text.
- `keywords_extracted` (`list[str]`): Model-segmented keywords.
- `contact_info_institution` (`str`): Name of the body handling applications.

!!! warning "Adding a field takes two edits"
    Pydantic drops keys the model does not declare, so a field added to `_aggregate_results` but not to `SearchMatch` disappears from the response without an error. Both must change together.

---

### Class `SearchResponse`

Top-level response wrapper returned by the search endpoints.

**Fields:**

- `matches` (`list[SearchMatch]`): Ordered list of matching projects sorted by descending `relative_score`.
- `weak_match` (`bool`, default `False`): True when nothing in the collection is a genuinely relevant match for the query — its best cosine falls below the collection's canary noise floor. This is the absolute signal `relative_score` cannot give: the top match scores `1.0` even for an off-topic query, so without this a nonsense query looks like a perfect hit. `False` also means "not known to be weak" — the check is skipped when the floor has not been measured yet. See `utils.search_service.is_weak_match`.

---
