"""Stage 1 — Sensitive Discovery. Favors recall; flags early signals."""

from __future__ import annotations

from datetime import datetime, timezone

from delta.models.radar import (
    Evidence, LifecycleState, RadarCandidate, Signals, count_independent_sources,
)
from delta.radar.signals import SignalNormalizer


def _age_hours(dt: datetime) -> float:
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 3600)


class Stage1Discovery:
    """Sensitive discovery stage — assigns DISCOVERED or WATCH state.

    Favors recall: insufficient early evidence should not automatically reject.
    A candidate with at least one fresh independent signal enters WATCH.
    """

    def __init__(self, radar_cfg: dict) -> None:
        s1_cfg = radar_cfg["stage1"]
        self._min_evidence = s1_cfg["min_evidence_to_watch"]
        self._min_independent = s1_cfg["min_independent_sources"]
        self._max_age_hours = s1_cfg["max_evidence_age_hours"]
        self._breakout_multiplier = s1_cfg["youtube_breakout_multiplier"]
        self._min_velocity = s1_cfg["min_view_velocity"]
        self._normalizer = SignalNormalizer(radar_cfg)

    def process(self, candidate: RadarCandidate) -> RadarCandidate:
        """Run Stage 1 on a candidate. Updates lifecycle, signals in-place."""
        evidence = candidate.evidence

        # Filter fresh evidence only
        fresh_evidence = [
            ev for ev in evidence
            if _age_hours(ev.observed_at) <= self._max_age_hours
        ]

        # Normalize signals from fresh evidence
        signals = self._normalizer.normalize(fresh_evidence, candidate.niche)
        candidate.signals = signals
        candidate.saturation_state = signals.saturation_state
        candidate.momentum_state = signals.momentum

        # Determine Stage 1 lifecycle
        if len(fresh_evidence) < self._min_evidence:
            candidate.lifecycle = LifecycleState.DISCOVERED
            return candidate

        independent_count = count_independent_sources(fresh_evidence)

        if independent_count >= self._min_independent:
            candidate.lifecycle = LifecycleState.WATCH
        else:
            candidate.lifecycle = LifecycleState.DISCOVERED

        return candidate
