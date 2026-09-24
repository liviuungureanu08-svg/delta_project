"""Radar scoring — deterministic opportunity + confidence scoring for RadarCandidates."""

from __future__ import annotations

from datetime import datetime, timezone

from delta.models.radar import (
    Evidence, MomentumState, RadarCandidate, SaturationState,
)


def _age_hours(dt: datetime) -> float:
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 3600)


_MOMENTUM_SCORE = {
    MomentumState.ACCELERATING: 1.0,
    MomentumState.RISING: 0.75,
    MomentumState.STABLE: 0.50,
    MomentumState.DECLINING: 0.10,
    MomentumState.UNKNOWN: 0.30,
}

_SATURATION_SCORE = {
    # Lower saturation = better opportunity gap
    SaturationState.EARLY: 1.00,
    SaturationState.EMERGING: 0.85,
    SaturationState.ACCELERATING: 0.65,
    SaturationState.MAINSTREAM: 0.35,
    SaturationState.SATURATED: 0.10,
}

_QUALITATIVE_SCORE = {
    "high": 1.0,
    "excellent": 1.0,
    "medium": 0.5,
    "good": 0.7,
    "low": 0.25,
    "unknown": 0.4,
}


def _q(value: str, default: float = 0.4) -> float:
    return _QUALITATIVE_SCORE.get((value or "").lower(), default)


class RadarScoring:
    """Scores RadarCandidates with separate opportunity and confidence scores."""

    def __init__(self, radar_cfg: dict) -> None:
        scoring_cfg = radar_cfg["scoring"]
        self._weights = scoring_cfg["weights"]
        self._conf_cfg = scoring_cfg["confidence"]

    def score(self, candidate: RadarCandidate) -> RadarCandidate:
        """Score candidate in-place. Returns candidate."""
        candidate.opportunity_score = round(self._score_opportunity(candidate), 3)
        candidate.confidence_score = round(self._score_confidence(candidate), 3)
        candidate.score_explanation = self._explain(candidate)
        return candidate

    def _score_opportunity(self, candidate: RadarCandidate) -> float:
        signals = candidate.signals
        w = self._weights

        momentum = _MOMENTUM_SCORE.get(signals.momentum, 0.3)
        saturation_gap = _SATURATION_SCORE.get(candidate.saturation_state, 0.5)

        freshness_days = signals.freshness_days
        if freshness_days is None:
            freshness = 0.4
        elif freshness_days <= 1:
            freshness = 1.0
        elif freshness_days <= 3:
            freshness = 0.85
        elif freshness_days <= 7:
            freshness = 0.65
        else:
            freshness = 0.30

        cross_source = 1.0 if signals.cross_source_confirmed else 0.3
        if signals.independent_source_count == 1:
            cross_source = 0.5

        audience = _q(signals.audience_relevance)
        monetization = _q(signals.monetization_strength)
        packaging = (
            _q(signals.title_potential) + _q(signals.thumbnail_potential)
        ) / 2.0

        score = (
            w["momentum"] * momentum
            + w["freshness"] * freshness
            + w["cross_source_confirmation"] * cross_source
            + w["saturation_gap"] * saturation_gap
            + w["audience_relevance"] * audience
            + w["monetization"] * monetization
            + w["packaging_potential"] * packaging
        )

        return min(1.0, max(0.0, score))

    def _score_confidence(self, candidate: RadarCandidate) -> float:
        c = self._conf_cfg
        conf = c["base"]

        # Independent source contribution
        independent_count = sum(
            1 for ev in candidate.evidence if ev.is_independent
        )
        conf += min(0.50, independent_count * c["per_independent_source"])

        # Cross-source confirmation bonus
        if candidate.signals.cross_source_confirmed:
            conf += c["cross_source_bonus"]

        # YouTube breakout bonus
        if candidate.signals.youtube_breakout:
            conf += c["youtube_breakout_bonus"]

        # Freshness bonus
        freshness_days = candidate.signals.freshness_days
        if freshness_days is not None and freshness_days <= c["freshness_threshold_days"]:
            bonus_days = c["freshness_threshold_days"] - freshness_days
            conf += bonus_days * c["freshness_bonus_multiplier"]

        return min(c["max"], max(0.0, conf))

    def _explain(self, candidate: RadarCandidate) -> list[str]:
        """Return human-readable score explanation components."""
        signals = candidate.signals
        reasons = []

        reasons.append(f"Momentum: {signals.momentum.value}")
        reasons.append(f"Saturation: {candidate.saturation_state.value}")
        reasons.append(f"Independent sources: {signals.independent_source_count}")

        if signals.cross_source_confirmed:
            reasons.append("Cross-source confirmed: YES")
        else:
            reasons.append("Cross-source confirmed: NO")

        if signals.youtube_breakout:
            mult = signals.channel_relative_multiplier
            reasons.append(
                f"YouTube breakout: {mult:.1f}x channel baseline"
                if mult else "YouTube breakout: YES"
            )

        freshness_days = signals.freshness_days
        if freshness_days is not None:
            reasons.append(f"Evidence freshness: {freshness_days}d old")

        reasons.append(f"Opportunity score: {candidate.opportunity_score:.3f}")
        reasons.append(f"Confidence score: {candidate.confidence_score:.3f}")

        return reasons
