"""Decide whether a new programme reaches a saved search's alert level.

A saved search stores a level *name* (broad / balanced / strict). Raw cosine
similarities from ``bge-m3`` are not comparable across queries — a short query scores
lower against everything than a long one — so a level is judged mostly **relative to
the query itself**. Two conditions have to hold:

* **Rank** — the new programme would rank among the top ``k`` of the *existing*
  programmes for this query. This absorbs the query-length shift (a short query's
  rank-``k`` cosine is lower too) and gives the level a meaning a user understands.
* **Noise floor** — its cosine clears what an off-topic query reaches in the same
  collection: the best cosine any :data:`CANARIES` query gets there, plus
  :data:`NOISE_MARGIN`. Rank alone cannot say a match is relevant, because *some*
  programme is always top-ranked, even for "cheesecake recipe". A z-score against the
  query's own distribution was tried and fails for the same reason: the best of a few
  thousand programmes is always 3-5 standard deviations above the mean.

The caller measures the :class:`QueryStats` and the collection's noise ceiling in
Qdrant; everything here is pure. No labels, no extra model and no stored calibration
are involved, so the result is deterministic for a given index.
"""

import bisect
import json
import logging
import os
from dataclasses import dataclass

from shared.alert_levels import LEVELS, normalize_level

logger = logging.getLogger(__name__)

# level -> k: "would rank among the top k existing programmes for this query".
DEFAULT_LEVEL_RULES: dict[str, int] = {"broad": 25, "balanced": 10, "strict": 3}

# How far above the collection's canary ceiling a match has to be. Sized from the
# spread of the canaries themselves: on the live index the best canary sits ~0.03 above
# the next one, so an unseen off-topic query could plausibly land that much above the
# worst one measured.
NOISE_MARGIN = float(os.getenv("ALERT_NOISE_MARGIN", "0.04"))

# Queries that should match no funding programme at all, per collection language.
# The best cosine any of them reaches in a collection is its noise ceiling. Short and
# long ones both: long queries score higher against everything, so a floor taken from
# short canaries alone would be too lenient for a long off-topic query.
CANARIES: dict[str, list[str]] = {
    "german": [
        "Rezept für Käsekuchen mit Quark",
        "Fußball Bundesliga Tabelle",
        "Wettervorhersage für das Wochenende",
        "Horoskop Sternzeichen Liebe",
        "asdf qwer zxcv uiop",
        "lorem ipsum dolor sit amet",
        "Mein Auto macht beim Bremsen ein quietschendes Geräusch und ich möchte wissen, "
        "ob ich die Bremsbeläge selbst wechseln kann oder lieber in die Werkstatt fahre.",
        "Welche Serien lohnen sich gerade im Streaming, wenn man spannende Krimis mag "
        "und am Wochenende mit Freunden einen gemütlichen Fernsehabend plant?",
        "Ich möchte meinem Hund beibringen, an der Leine nicht mehr zu ziehen, und suche "
        "Tipps für das Training im Park, wenn andere Hunde in der Nähe sind.",
        "Können Sie mir erklären, wie ich in einer Tabellenkalkulation eine Formel "
        "schreibe, die Werte aus einer anderen Tabelle sucht und sie zusammenzählt?",
    ],
    "eu": [
        "recipe for cheesecake with quark",
        "football league table",
        "weather forecast for the weekend",
        "horoscope zodiac love",
        "asdf qwer zxcv uiop",
        "lorem ipsum dolor sit amet",
        "My car makes a squealing noise when I brake and I would like to know whether I "
        "can replace the brake pads myself or should take it to a garage.",
        "Which series are worth watching on streaming right now if you like gripping "
        "crime dramas and are planning a cosy evening in with friends at the weekend?",
        "I would like to teach my dog to stop pulling on the lead and am looking for "
        "training tips for the park when other dogs are nearby.",
        "Could you explain how to write a spreadsheet formula that looks up values in "
        "another sheet and adds them up for me?",
    ],
}


def _load_level_rules() -> dict[str, int]:
    """Read ``ALERT_LEVEL_RULES`` (JSON ``{"level": k}``) over the defaults.

    An invalid value is logged and ignored rather than aborting startup: the defaults
    are always a usable fallback.
    """
    rules = dict(DEFAULT_LEVEL_RULES)
    raw = os.getenv("ALERT_LEVEL_RULES", "").strip()
    if not raw:
        return rules
    try:
        for level, k in json.loads(raw).items():
            if level not in LEVELS or isinstance(k, bool) or int(k) != k or k < 1:
                raise ValueError(f"bad rule for {level!r}")
            rules[level] = int(k)
    except (ValueError, TypeError, AttributeError) as exc:
        logger.error("Ignoring invalid ALERT_LEVEL_RULES %r: %s", raw, exc)
        return dict(DEFAULT_LEVEL_RULES)
    return rules


LEVEL_RULES = _load_level_rules()

# Existing programmes whose cosine the rank condition needs: the loosest level's k.
RANK_DEPTH = max(LEVEL_RULES.values())


@dataclass(frozen=True)
class QueryStats:
    """How one query scores against a collection.

    Attributes:
        rank_cosines (tuple[float, ...]): Best-chunk cosines of the top existing
            programmes, highest first, :data:`RANK_DEPTH` long unless the
            collection is smaller.
        noise_floor (float): The collection's canary ceiling plus
            :data:`NOISE_MARGIN`; see :func:`noise_floor`.
    """

    rank_cosines: tuple[float, ...]
    noise_floor: float


@dataclass(frozen=True)
class Verdict:
    """Why a candidate did or did not reach a level.

    Attributes:
        passed (bool): Both conditions hold.
        rank (int): Existing programmes that score higher than the candidate, i.e.
            the 0-based position it would take among them. Capped at the number of
            cosines in :attr:`QueryStats.rank_cosines`, so ``RANK_DEPTH`` means
            "that deep or deeper".
        above_noise (bool): The cosine clears the noise floor.
    """

    passed: bool
    rank: int
    above_noise: bool


def noise_floor(canary_top1: list[float]) -> float:
    """Return the noise floor for a collection from its canaries' best cosines.

    The ceiling is the *maximum*, not a percentile: with a handful of canaries a
    percentile is barely more than the maximum anyway, and erring high costs a
    borderline alert rather than sending a false one.

    Raises:
        ValueError: No canary could be scored, so there is no floor to judge by.
    """
    if not canary_top1:
        raise ValueError("no canary scores to derive a noise floor from")
    return max(canary_top1) + NOISE_MARGIN


def judge(level: object, cosine: float, stats: QueryStats) -> Verdict:
    """Judge one candidate's best-chunk cosine against a level for one query.

    Args:
        level (object): Level name; anything unknown means the default level.
        cosine (float): The candidate's best-chunk cosine to the query.
        stats (QueryStats): The query's ranking and the collection's noise floor.

    Returns:
        Verdict: Whether it passes, with the rank and noise check it was judged on.
    """
    k = LEVEL_RULES[normalize_level(level)]
    # rank_cosines is descending; count the entries strictly above ``cosine``.
    rank = bisect.bisect_left([-c for c in stats.rank_cosines], -cosine)
    above_noise = cosine >= stats.noise_floor
    return Verdict(passed=rank < k and above_noise, rank=rank, above_noise=above_noise)


__all__ = [
    "CANARIES", "DEFAULT_LEVEL_RULES", "LEVEL_RULES", "NOISE_MARGIN", "QueryStats",
    "RANK_DEPTH", "Verdict", "judge", "noise_floor",
]
