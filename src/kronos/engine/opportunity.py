"""Opportunity Engine — scores TopicCandidates deterministically."""

from __future__ import annotations

from typing import Optional

from kronos.config import scoring_config, channel_config
from kronos.models.topic import TopicCandidate


_QUALITATIVE_SCORE = {
    # demand trend
    "rising": 1.0,
    "stable": 0.6,
    "falling": 0.2,
    # freshness
    "very fresh": 1.0,
    "fresh": 0.8,
    "evergreen": 0.5,
    "dated": 0.1,
    # saturation (inverted — lower saturation is better)
    "low": 1.0,
    "medium": 0.5,
    "high": 0.1,
    # monetization / title / thumbnail
    "excellent": 1.0,
    "high": 0.85,
    "good": 0.7,
    "medium": 0.5,
    "low": 0.25,
    "unknown": 0.4,
}


def _q(value: Optional[str], default: float = 0.4) -> float:
    if value is None:
        return default
    return _QUALITATIVE_SCORE.get(value.lower(), default)


class OpportunityEngine:
    def __init__(self) -> None:
        self._cfg = scoring_config()["scoring"]
        self._weights = self._cfg["weights"]
        self._thresholds = self._cfg["thresholds"]
        self._channel = channel_config()

    def score(self, candidate: TopicCandidate) -> TopicCandidate:
        """Score a TopicCandidate in-place and return it."""
        weights = self._weights

        audience_relevance = _q(candidate.audience_relevance)
        demand_signal = _q(candidate.demand.search_trend)
        freshness = _q(candidate.freshness)
        competition_gap = _q(candidate.competition.saturation)   # low saturation = good gap
        monetization = _q(candidate.monetization_potential)
        title_thumb = (
            _q(candidate.title_potential) + _q(candidate.thumbnail_potential)
        ) / 2.0

        score = (
            weights["audience_relevance"] * audience_relevance
            + weights["demand_signal"] * demand_signal
            + weights["freshness"] * freshness
            + weights["competition_gap"] * competition_gap
            + weights["monetization_potential"] * monetization
            + weights["title_thumbnail_potential"] * title_thumb
        )

        evidence_count = len(candidate.available_evidence)
        # Confidence grows with evidence, floored at configured minimum
        confidence = min(
            self._cfg["confidence_ceil"],
            max(
                self._cfg["confidence_floor"],
                0.3 + 0.1 * evidence_count,
            ),
        )

        candidate.opportunity_score = round(score, 3)
        candidate.confidence = round(confidence, 3)
        candidate.recommended_formats = self._recommend_formats(candidate)
        return candidate

    def is_worth_proceeding(self, candidate: TopicCandidate) -> bool:
        return candidate.opportunity_score >= self._thresholds["minimum_score_to_proceed"]

    def _recommend_formats(self, candidate: TopicCandidate) -> list[str]:
        formats = []
        score = candidate.opportunity_score
        freshness = (candidate.freshness or "").lower()

        if freshness in ("very fresh", "fresh") and score >= 0.5:
            formats.append("SHORT")

        if score >= 0.55:
            formats.append("UTILITY_LONG_FORM")

        if score >= 0.65 and freshness not in ("dated",):
            formats.append("INSTAGRAM_POST")

        if score >= 0.70:
            formats.append("INSTAGRAM_CAROUSEL")

        if score >= 0.75:
            formats.append("DOCUMENTARY")

        return formats
