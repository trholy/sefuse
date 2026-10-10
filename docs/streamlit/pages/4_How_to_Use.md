# `streamlit.pages.4_How_to_Use`

Static informational page that teaches users how to write effective semantic search queries for the funding databases.

Applies auth guards, then renders five sections. Page config is set by `Home.py`.

---

### `_render_core_problem() -> None`

Explains the asymmetric embedding space problem: funding documents use administrative bureaucratic language (Verwaltungssprache) — eligibility criteria, thematic priorities, funding instruments, and funding conditions — while applicant project descriptions use scientific-innovative technical language. Motivates users to write queries that bridge both registers.

**Returns:** `None`

---

### `_render_quality_criteria() -> None`

Describes four characteristics of a high-quality search query:

1. Mirror funding program taxonomy along five axes: thematic priority area (Handlungsfeld), technology readiness level / project phase (Technologiereifegrad / Vorhabensphase), eligible recipient type (Zuwendungsempfänger), sector / application domain (Branche / Anwendungsbereich), and funding instrument (Förderinstrument).
2. Combine precise technical terms with broader plain-language equivalents to increase recall across both retrieval channels.
3. State outcomes and impact goals (Wirkungsziele) alongside methods, using goal-oriented phrasings.
4. Explicitly declare organizational context: company size, legal form (Rechtsform), collaborative nature (Verbundcharakter), and geographic reference (Bundesland).

**Returns:** `None`

---

### `_render_template() -> None`

Presents a structured English/German mixed-language query template covering all taxonomy axes and a filled example that describes a Bavarian KMU developing an AI-based plant-disease detection system.

**Returns:** `None`

---

### `_render_anti_patterns() -> None`

Renders a table of five common anti-patterns — exclusive technical jargon, method-only descriptions, missing organization type, very short queries, and English queries against a German corpus — with their problems and recommended fixes.

**Returns:** `None`

---

### `_render_advanced() -> None`

Describes automatic LLM-based query expansion (Förderberater system prompt) as an optional pre-embedding step, noting a typical 15–25 % recall improvement before downstream re-ranking (Neugewichtung).

**Returns:** `None`

---

### `_render_eu_adaptation() -> None`

Explains how the query design approach must be adjusted when searching EU funding programs (Horizon Europe, ERDF I3 Instrument, sector-specific calls). Covers four sub-topics:

1. **Taxonomy shift** — EU calls use TRL ranges, consortium requirements, policy alignment (Green Deal, Competitiveness Compass, S3), and strand designations instead of Zuwendungsempfänger / Handlungsfelder / Förderinstrumente.
2. **Heterogeneous register** — EU texts mix dense procedural language with mission-driven communication; pure administrative vocabulary matching is less reliable. Outcome-oriented phrasings (*contributing to*, *strengthening resilience*, *accelerating market uptake*) should be included.
3. **Organizational framing** — EU programs filter by consortium structure, geographic spread, and sectoral role rather than company size (KMU) and legal form (Rechtsform).
4. **Policy keyword alignment** — named EU frameworks (Smart Specialisation Strategy, European Green Deal, Cohesion Policy, Food 2030) function like Handlungsfeld labels and should be explicitly referenced.

Renders an adapted EU query template covering consortium type, actor types, regional development status, thematic priority, TRL range, policy alignment, funding instrument, and geographic scope. Closes with a note that LLM-based query expansion remains valuable but the prompt must target EU policy vocabulary, TRL framing, and consortium logic.

**Returns:** `None`

---

## Module-level execution

| Step | Action |
|---|---|
| 1 | `safe_bootstrap()` — initialises session state; stops on failure. |
| 2 | `require_login()` — stops unauthenticated users. |
| 3 | `render_logout_button()` — sidebar logout control. |
| 4 | Renders title and all six content sections. |
