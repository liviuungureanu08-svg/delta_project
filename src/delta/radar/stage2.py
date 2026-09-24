"""Stage 2 — Validation. Skeptical false-positive reduction."""

from __future__ import annotations

from datetime import datetime, timezone

from delta.models.radar import (
    Evidence, LifecycleState, RadarCandidate, count_independent_sources,
)


def _age_hours(dt: datetime) -> float:
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 3600)


def _avg_confidence(evidence: list[Evidence]) -> float:
    if not evidence:
        return 0.0
    return sum(ev.confidence for ev in evidence) / len(evidence)


def _count_independent(evidence: list[Evidence]) -> int:
    """Count independent sources, deduplicating by channel/outlet identity."""
    return count_independent_sources(evidence)


def _is_single_large_channel_spike(evidence: list[Evidence], large_threshold: int) -> bool:
    """True if only one channel contributed YouTube signals and it's a large channel."""
    yt_channels: set[str] = set()
    all_large = True
    for ev in evidence:
        if ev.source_type != "youtube":
            continue
        p = ev.observed_value
        if not isinstance(p, dict):
            continue
        ch_id = p.get("channel_id", ev.source_id)
        yt_channels.add(ch_id)
        baseline = p.get("channel_baseline_views", 0)
        if baseline < large_threshold:
            all_large = False

    if len(yt_channels) <= 1 and all_large and yt_channels:
        return True
    return False


class Stage2Validation:
    """Validation stage — moves WATCH → VALIDATED or keeps WATCH / REJECTED.

    Cross-niche uses stricter thresholds than AI/Tech primary niche.
    """

    def __init__(self, radar_cfg: dict) -> None:
        s2_cfg = radar_cfg["stage2"]
        self._ai_tech_cfg = s2_cfg["ai_tech"]
        self._cross_niche_cfg = s2_cfg["cross_niche"]
        fp_cfg = radar_cfg.get("false_positive", {})
        self._large_ch_threshold = fp_cfg.get("large_channel_baseline_threshold", 100_000)
        self._stale_hours = fp_cfg.get("stale_signal_hours", 120)

    def process(self, candidate: RadarCandidate) -> RadarCandidate:
        """Validate a WATCH candidate. Returns candidate with updated lifecycle."""
        if candidate.lifecycle not in (LifecycleState.WATCH, LifecycleState.VALIDATED):
            return candidate

        niche_cfg = (
            self._cross_niche_cfg
            if candidate.niche == "cross_niche"
            else self._ai_tech_cfg
        )

        evidence = candidate.evidence
        fresh_evidence = [
            ev for ev in evidence
            if _age_hours(ev.observed_at) <= niche_cfg["max_evidence_age_hours"]
        ]

        # False-positive guard: single large channel spike
        if _is_single_large_channel_spike(evidence, self._large_ch_threshold):
            candidate.lifecycle = LifecycleState.WATCH
            candidate.main_risk = (
                "Signal from a single large channel performing at normal baseline — "
                "insufficient independent breakout evidence."
            )
            return candidate

        # Stale signal guard
        fresh_independent = [
            ev for ev in fresh_evidence
            if ev.is_independent and _age_hours(ev.observed_at) <= self._stale_hours
        ]

        independent_count = _count_independent(fresh_independent)
        avg_conf = _avg_confidence(fresh_independent)

        min_sources = niche_cfg["min_independent_sources_for_validation"]
        min_conf = niche_cfg["min_avg_evidence_confidence"]
        min_score = niche_cfg["min_opportunity_score"]

        reasons: list[str] = []

        if independent_count < min_sources:
            reasons.append(
                f"Only {independent_count} independent source(s); need {min_sources}."
            )
        if avg_conf < min_conf:
            reasons.append(
                f"Average evidence confidence {avg_conf:.2f} < {min_conf} required."
            )
        if candidate.opportunity_score < min_score:
            reasons.append(
                f"Opportunity score {candidate.opportunity_score:.3f} < {min_score} required."
            )

        if reasons:
            candidate.lifecycle = LifecycleState.WATCH
            candidate.main_risk = " ".join(reasons)
        else:
            candidate.lifecycle = LifecycleState.VALIDATED
            candidate.main_risk = None

        return candidate
