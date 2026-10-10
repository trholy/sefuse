"""Request and response models for the search API.

Pydantic validates these before a route handler runs, so a malformed request is
rejected with a 422 without reaching the search path at all.

Both collections are served through one ``SearchMatch``: the German and EU payloads
do not carry the same keys, so the fields only one of them has are defaulted rather
than split into two models. ``fastapi/src/utils/config.py`` holds the matching
``PAYLOAD_DISPLAY_FIELDS``, and a test asserts the two agree in both directions — a
field added here but not there would never trigger a payload refresh.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .config import EMBED_MODEL


class SearchFilters(BaseModel):
    """Optional taxonomy filters applied server-side before returning search results.

    All list fields accept human-readable taxonomy values; the backend normalises
    them to canonical keys via ``taxonomy_key_set`` before comparing. Each field
    is matched with OR within the field and AND across fields.

    Fields:
        funding_type: Allowed funding types (e.g. ``["Zuschuss"]``). None means no filter.
        funding_area: Allowed funding areas. None means no filter.
        funding_location: Allowed funding locations. None means no filter.
        eligible_applicants: Allowed applicant categories. None means no filter.
        drop_na: When True, results where both short and full description are
            ``"N/A"`` are excluded. Defaults to False.
    """

    funding_type: list[str] | None = None
    funding_area: list[str] | None = None
    funding_location: list[str] | None = None
    eligible_applicants: list[str] | None = None
    drop_na: bool = False

    @field_validator("funding_type", "funding_area", "funding_location", "eligible_applicants")
    @classmethod
    def _cap_element_length(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        return [s for s in v if len(s) <= 64][:50]


class SearchMessage(BaseModel):
    """A single chat-style message that carries the user's search query.

    Fields:
        role: Always ``"user"``; other values are rejected by Pydantic.
        content: The search query text. Must be between 1 and 5 000 characters.
    """

    role: Literal["user"] = "user"
    content: str = Field(min_length=1, max_length=5000)


class SearchRequest(BaseModel):
    """Validated request body for search endpoints.

    FastAPI automatically rejects requests that violate any constraint with a
    422 Unprocessable Entity response before the route handler is called.

    Fields:
        messages: Conversation history. Must contain 1–8 ``SearchMessage`` items;
            the first item's ``content`` is used as the search query.
        model: Ollama model name to use for query embedding (e.g. ``"bge-m3"``).
        limit: Number of results to return. Must be between 1 and 100. Defaults to 20.
        semantic_weight: Blend weight between dense (1.0) and sparse (0.0) search.
            Must be in [0.0, 1.0]. Defaults to 0.7.
        filters: Optional taxonomy filters. Defaults to an empty ``SearchFilters``
            (no filtering).
    """

    messages: list[SearchMessage] = Field(min_length=1, max_length=8)
    model: str
    limit: int = Field(ge=1, le=100, default=20)
    semantic_weight: float = Field(ge=0.0, le=1.0, default=0.7)
    filters: SearchFilters = Field(default_factory=SearchFilters)

    @field_validator("model")
    @classmethod
    def _validate_model(cls, v: str) -> str:
        if v != EMBED_MODEL:
            raise ValueError(
                f"Unsupported model '{v}'. Server is configured to use '{EMBED_MODEL}'."
            )
        return v


class SearchMatch(BaseModel):
    """A single funding project result returned by the search endpoints.

    ``relative_score`` is normalised to [0, 1] against the top result *in this
    response*, after filtering. It is a within-response ranking signal and nothing
    more: the best match always scores 1.0, however poor it is in absolute terms, and
    a score is not comparable between two responses. ``SearchResponse.weak_match``
    is the absolute companion to it.

    Fields:
        project_id: UUID of the funding project.
        project_title: Human-readable project title.
        project_short_description: Short summary of the funding program.
        project_full_description: Full description text of the funding program.
        date_1: First relevant date string (e.g. application deadline).
        date_2: Second relevant date string (e.g. funding period end).
        funding_type: Human-readable funding type labels.
        funding_area: Human-readable funding area labels.
        funding_location: Human-readable funding location labels.
        eligible_applicants: Human-readable eligible applicant labels.
        funding_type_keys: Normalised taxonomy keys for ``funding_type``.
        funding_area_keys: Normalised taxonomy keys for ``funding_area``.
        funding_location_keys: Normalised taxonomy keys for ``funding_location``.
        eligible_applicants_keys: Normalised taxonomy keys for ``eligible_applicants``.
        project_website: URL of the funding program's detail page.
        relative_score: Rank signal in [0, 1], relative to this response's best match.
        topic_destination: Aims of the work programme destination the topic sits
            under. EU collection only, and stated on Horizon topics only.
        status_note: Editorial status banner, e.g. "Programm aktiv, Antragstellung
            nicht möglich". German collection only.
        deadlines: Application deadline text. German collection only.
        keywords_extracted: Model-segmented keywords. German collection only.
        contact_info_institution: Name of the body handling applications. German
            collection only.
    """

    project_id: str
    project_title: str
    project_short_description: str
    project_full_description: str
    date_1: str
    date_2: str
    funding_type: list[str]
    funding_area: list[str]
    funding_location: list[str]
    eligible_applicants: list[str]
    funding_type_keys: list[str]
    funding_area_keys: list[str]
    funding_location_keys: list[str]
    eligible_applicants_keys: list[str]
    project_website: str
    relative_score: float
    # EU-only field, defaulted for the same reason the German-only ones below are:
    # the German collection carries no such payload key. Stated on Horizon topics
    # only, so it is empty for most EU results too.
    topic_destination: str = ""
    # German-only fields. Defaulted because the EU collection carries no such payload
    # keys, and both collections are served through this one response model.
    status_note: str = ""
    deadlines: str = ""
    keywords_extracted: list[str] = []
    contact_info_institution: str = ""


class SearchResponse(BaseModel):
    """Top-level response wrapper returned by the search endpoints.

    Fields:
        matches: Ordered list of matching funding projects, sorted by descending
            ``relative_score``. Empty when no results satisfy the query and filters.
        weak_match: True when nothing in the collection is a genuinely relevant
            match for the query — its best cosine falls below the collection's
            canary noise floor. This is the absolute signal ``relative_score``
            cannot give: the top match scores 1.0 even for an off-topic query, so
            without this a nonsense query looks like a perfect hit. False also
            means "not known to be weak": the check is skipped when the floor has
            not been measured yet. See ``utils.search_service.is_weak_match``.
    """

    matches: list[SearchMatch]
    weak_match: bool = False
