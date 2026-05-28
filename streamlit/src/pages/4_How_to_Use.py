import streamlit as st

from auth.handlers import (
    safe_bootstrap,
    render_logout_button,
    require_login,
)

st.set_page_config(
    page_title="SeFuSe - How to Use",
    layout="centered",
    page_icon="favicon.jpg",
)


def _render_core_problem() -> None:
    st.header("The Core Problem: Asymmetric Embedding Space")
    st.write(
        "Funding program documents are written in administrative bureaucratic language "
        "(Verwaltungssprache) - they describe eligibility criteria (Zuwendungsvoraussetzungen), "
        "thematic priorities (Themenschwerpunkte), funding instruments (Förderinstrumente), "
        "and funding conditions (Förderbedingungen). Project descriptions submitted by applicants, "
        "on the other hand, are formulated in scientific-innovative technical language. "
        "The embedding model maps both text types into the same vector space, but the semantic "
        "distance between them depends on the degree of vocabulary overlap and the alignment of "
        "both registers.\n\n"
        "**The goal is to formulate search queries that bridge both language registers.**"
    )


def _render_quality_criteria() -> None:
    st.header("Characteristics of a High-Quality Search Query")

    st.subheader("1. Mirror the taxonomy of funding programs")
    st.write(
        "Funding programs are structured along specific axes. "
        "A well-formed search query should explicitly address all relevant dimensions:"
    )
    st.markdown(
        "- **Thematic priority area (Handlungsfeld)** - e.g. *Künstliche Intelligenz*, "
        "*nachhaltige Mobilität*, *medizinische Diagnostik*\n"
        "- **Technology readiness level / project phase (Technologiereifegrad / Vorhabensphase)** - "
        "e.g. *Grundlagenforschung*, *angewandte Forschung*, *Pilotprojekt*, *Demonstrator*\n"
        "- **Type of eligible recipient (Zuwendungsempfänger)** - "
        "e.g. *KMU*, *Hochschule*, *Konsortium*, *Start-up*\n"
        "- **Sector / application domain (Branche / Anwendungsbereich)** - "
        "e.g. *Gesundheitswirtschaft*, *Luft- und Raumfahrt*, *Landwirtschaft*\n"
        "- **Funding instrument (Förderinstrument)** - "
        "e.g. *Zuschuss*, *Darlehen*, *Beteiligungskapital*"
    )

    st.subheader("2. Combine general and specific vocabulary")
    st.write(
        "Semantic models generalize well; lexical components in hybrid search queries do not. "
        "Using the precise technical term alongside the broader concept increases recall: "
        "*computer vision / Bildverarbeitung / automatische Erkennung* "
        "covers a wider semantic surface area."
    )

    st.subheader("3. State outcomes and impact goals, not just methods")
    st.write(
        "Funding programs describe objectives and intended effects (Wirkungsziele). "
        "A query that only describes the method employed will miss programs oriented toward "
        "concrete results. Goal-oriented phrasings such as *um ... zu ermöglichen*, "
        "*mit dem Ziel*, or *zur Verbesserung von* should therefore be explicitly included."
    )

    st.subheader("4. Explicitly state the organizational context")
    st.write(
        "Many funding programs are restricted to specific eligible recipients. "
        "The search query should always include: company size, legal form (Rechtsform), "
        "the collaborative nature of the project (Verbundcharakter), "
        "and geographic reference (federal state / Bundesland, where relevant)."
    )


def _render_template() -> None:
    st.header("Query Template")
    st.write("Use this structure as a starting point for German federal funding searches:")
    st.code(
        "[Organisationstyp] with [Größe/Rechtsform] is developing [Technologie/Methode]\n"
        "in the field of [Themenfeld] with the goal of [konkretes Ergebnis/Anwendung].\n\n"
        "The project is currently in the phase of [Grundlagenforschung /\n"
        "angewandte Forschung / Entwicklung / Pilot / Markteinführung].\n\n"
        "Application domain: [Branche / Sektor].\n"
        "Cooperation partners: [Hochschule / weitere KMU / keine].\n"
        "Funding need: [Zuschuss / Darlehen / Beratung].",
        language=None,
    )


def _render_anti_patterns() -> None:
    st.header("Common Query Anti-Patterns")
    st.table(
        [
            {
                "Anti-pattern": "Exclusively technical jargon (e.g. 'transformer-based multi-modal fusion')",
                "Problem": "No lexical overlap with program text (Programmtext)",
                "Fix": "Add plain-language equivalents",
            },
            {
                "Anti-pattern": "Method description only, no application reference",
                "Problem": "Sector-specific programs (branchenspezifische Programme) are not retrieved",
                "Fix": "Add Anwendungsbereich",
            },
            {
                "Anti-pattern": "Missing organization type (Organisationstyp)",
                "Problem": "Eligibility-filtered programs are bypassed",
                "Fix": "Always include KMU / Hochschule / institution type",
            },
            {
                "Anti-pattern": "Very short single-sentence queries",
                "Problem": "Insufficient signal for embedding",
                "Fix": "Aim for a [minimum of 80–150 tokens](https://platform.openai.com/tokenizer)",
            },
            {
                "Anti-pattern": "English query against a German corpus",
                "Problem": "Significantly reduced embedding quality",
                "Fix": "Match the language of the corpus (Korpussprache)",
            },
        ]
    )


def _render_eu_adaptation() -> None:
    st.header("Adapting the Approach for EU Funding Programs")
    st.write(
        "When searching across EU funding programs - such as Horizon Europe calls, the I3 Instrument "
        "under the ERDF, or sector-specific calls - several of the core principles still apply, "
        "but the taxonomy, register, and structural logic of the corpus shift considerably, "
        "requiring adjustments to query design."
    )

    st.subheader("The taxonomy changes significantly")
    st.write(
        "German Förderprogramme are structured around Zuwendungsempfänger, Handlungsfelder, and "
        "Förderinstrumente. EU funding calls, by contrast, organize eligibility and scope around "
        "different axes: TRL ranges (e.g. *TRL 6 to TRL 9*), consortium requirements "
        "(multi-actor, quadruple helix, interregional), policy alignment (Green Deal, "
        "Competitiveness Compass, Smart Specialisation Strategies / S3), and strand or pillar "
        "designations (e.g. *Strand 1*, *Strand 2a*). A well-formed query for EU programs must "
        "therefore replace or supplement the Organisationstyp / KMU framing with explicit references "
        "to consortium composition, regional development status (less developed, transition, or more "
        "developed regions), and alignment with named EU policy frameworks."
    )

    st.subheader("The language register of the corpus is more heterogeneous")
    st.write(
        "EU funding texts range from dense procedural-institutional language to more accessible, "
        "mission-driven policy communication. This means that pure administrative vocabulary "
        "matching - effective in the German Förderdatenbank context - is less reliable. "
        "Queries should additionally incorporate the outcome-oriented and impact-driven phrasings "
        "characteristic of EU calls: *contributing to*, *strengthening resilience*, "
        "*accelerating market uptake*, *fostering interregional cooperation*."
    )

    st.subheader("Organizational context requires a different framing")
    st.write(
        "Where German programs filter primarily by company size (KMU) and legal form (Rechtsform), "
        "EU programs filter by consortium structure, geographic spread, and sectoral role. "
        "Queries should therefore explicitly state whether the applicant leads a consortium, "
        "which regions are involved, and what role SMEs play relative to research institutions "
        "and public authorities - as these are primary eligibility and scoring dimensions."
    )

    st.subheader("Policy keyword alignment becomes critical")
    st.write(
        "EU call texts are densely cross-referenced with named strategies, initiatives, and "
        "frameworks. Including explicit references to relevant frameworks - such as "
        "*Smart Specialisation Strategy*, *European Green Deal*, *Cohesion Policy*, or *Food 2030* "
        "- functions similarly to including Handlungsfeld labels in the German context: "
        "it narrows the semantic match toward the most relevant program families."
    )

    st.subheader("Adapted Query Template for EU Funding")
    st.write("Use this structure as a starting point for EU funding searches:")
    st.code(
        "A [consortium type] consisting of [actor types, e.g. SMEs, universities,\n"
        "regional authorities] from [regions / development status] is developing\n"
        "[technology/solution] in the field of [thematic priority: digital transition /\n"
        "green transition / agri-food / etc.] with the goal of [concrete outcome /\n"
        "market uptake / deployment].\n\n"
        "The project operates at TRL [X] and aims to reach TRL [Y].\n\n"
        "Policy alignment: [e.g. European Green Deal, Competitiveness Compass,\n"
        "Smart Specialisation Strategy, Food 2030].\n"
        "Funding instrument sought: [grant / cascade funding / blended finance].\n"
        "Geographic scope: [interregional / transnational / specific Member States].",
        language=None,
    )


safe_bootstrap()

require_login()
render_logout_button()

st.title("How to Use: Writing Effective Search Queries")
_render_core_problem()
_render_quality_criteria()
_render_template()
_render_anti_patterns()
_render_eu_adaptation()
