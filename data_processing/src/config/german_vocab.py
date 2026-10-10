"""Closed vocabularies of the Förderdatenbank export: category code → German label.

The published CSV states each taxonomy as a *code* (``zuschuss``), not as a display
name (``Zuschuss``). These maps turn the codes back into the labels the UI shows and
`TaxonomyContractBuilder` canonicalises.

Provenance
----------
Copied from ``fdb_scraper/src/fdb_scraper/generated/vocab.py`` (CorrelAid,
https://github.com/CorrelAid/fdb_scraper). That file is itself generated from an
extracted export by ``scripts/gen_vocab.py`` and committed upstream, so any change to
a category list shows up there as a reviewable diff. Re-sync from it when the
Förderdatenbank adds or relabels a category — a code with no entry here is not lost:
``GermanFundingCsvParser`` keeps unknown codes verbatim so they surface in the
taxonomy artifact as a recognisable slug.

Codes are kept exactly as upstream ships them, including the ``schlesig_holstein``
typo and the ``de_ni`` / ``de_st`` NUTS-style outliers, so a lookup either matches the
source or honestly misses.
"""

# Förderart — what form the funding takes.
FOERDERART: dict[str, str] = {
    "beteiligung": "Beteiligung",
    "buergschaft": "Bürgschaft",
    "darlehen": "Darlehen",
    "garantie": "Garantie",
    "sonstige": "Sonstige",
    "zuschuss": "Zuschuss",
}

# Förderberechtigte — who may apply.
FOERDERBERECHTIGTE: dict[str, str] = {
    "bildungseinrichtung": "Bildungseinrichtung",
    "existenzgruenderin": "Existenzgründer/in",
    "forschungseinrichtung": "Forschungseinrichtung",
    "hochschule": "Hochschule",
    "kommune": "Kommune",
    "oeffentliche_einrichtung": "Öffentliche Einrichtung",
    "privatperson": "Privatperson",
    "unternehmen": "Unternehmen",
    "verband_vereinigung": "Verband/Vereinigung",
}

# Förderbereich — the thematic area.
FOERDERBEREICH: dict[str, str] = {
    "arbeit": "Arbeit",
    "aus_weiterbildung": "Aus- & Weiterbildung",
    "aussenwirtschaft": "Außenwirtschaft",
    "beratung": "Beratung",
    "corona": "Corona-Hilfe",
    "digitalisierung": "Digitalisierung",
    "energieeffizienz_erneuerbare_energien": "Energieeffizienz & Erneuerbare Energien",
    "existenzgruendung_festigung": "Existenzgründung & -festigung",
    "forschung_innovation_themenoffen": "Forschung & Innovation (themenoffen)",
    "forschung_innovation_themenspezifisch": "Forschung & Innovation (themenspezifisch)",
    "frauenfoerderung": "Frauenförderung",
    "gesundheit_soziales": "Gesundheit & Soziales",
    "infrastruktur": "Infrastruktur",
    "kultur_medien_sport": "Kultur, Medien & Sport",
    "landwirtschaft_laendliche_entwicklung": "Landwirtschaft & Ländliche Entwicklung",
    "messen_ausstellungen": "Messen & Ausstellungen",
    "mobilitaet": "Mobilität",
    "regionalfoerderung": "Regionalförderung",
    "smart_cities_regionen": "Smart Cities & Regionen",
    "staedtebau_stadterneuerung": "Städtebau & Stadterneuerung",
    "umwelt_naturschutz": "Umwelt- & Naturschutz",
    "unternehmensfinanzierung": "Unternehmensfinanzierung",
    "wohnungsbau_modernisierung": "Wohnungsbau & -modernisierung",
}

# Fördergeber — which level of government funds the programme.
FOERDERGEBER: dict[str, str] = {
    "bund": "Bund",
    "eu": "EU",
    "land": "Land",
}

# Fördergebiet — the Bundesland, or nationwide scope.
#
# Two deliberate departures from the upstream file:
#   * ``_bundesweit`` is labelled "Bundesweit" here, not upstream's lowercase
#     "bundesweit", so it reads like the Bundesland labels beside it in the UI.
#   * ``bundesweit`` (without the underscore) is kept as an alias. Upstream collapses
#     the duplicate category into ``_bundesweit`` before publishing, so the CSV should
#     never carry it — but mapping it costs nothing and avoids a raw slug leaking into
#     the filter sidebar if that ever changes.
FOERDERGEBIET: dict[str, str] = {
    "_bundesweit": "Bundesweit",
    "bundesweit": "Bundesweit",
    "baden_wuerttemberg": "Baden-Württemberg",
    "bayern": "Bayern",
    "berlin": "Berlin",
    "brandenburg": "Brandenburg",
    "bremen": "Bremen",
    "de_ni": "Niedersachsen",
    "de_st": "Sachsen-Anhalt",
    "hamburg": "Hamburg",
    "hessen": "Hessen",
    "mecklenburg_vorpommern": "Mecklenburg-Vorpommern",
    "nordrhein_westfalen": "Nordrhein-Westfalen",
    "rheinland_pfalz": "Rheinland-Pfalz",
    "saarland": "Saarland",
    "sachsen": "Sachsen",
    "schlesig_holstein": "Schleswig-Holstein",
    "sonstige": "Sonstige",
    "thueringen": "Thüringen",
}

# SeFuSe column name → the vocabulary that decodes it. Keyed by the *output* column so
# the parser maps by column rather than by remembering which import belongs where.
CODE_LABELS: dict[str, dict[str, str]] = {
    "funding_type": FOERDERART,
    "funding_area": FOERDERBEREICH,
    "funding_location": FOERDERGEBIET,
    "eligible_applicants": FOERDERBERECHTIGTE,
    "funding_body": FOERDERGEBER,
}
