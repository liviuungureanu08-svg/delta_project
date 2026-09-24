"""Signal normalization — converts raw SourceEvidence into Signals for a RadarCandidate."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from delta.models.radar import (
    Evidence, MomentumState, RadarCandidate, SaturationState, Signals,
)
from delta.radar.providers.base import SourceEvidence
from delta.radar.saturation import SaturationClassifier


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _age_hours(dt: datetime) -> float:
    now = _now()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 3600)


def evidence_from_source(se: SourceEvidence) -> Evidence:
    return Evidence(
        source_type=se.source_type,
        source_id=se.source_id,
        observed_at=se.observed_at,
        evidence_type=se.evidence_type,
        observed_value=se.payload,
        confidence=se.base_confidence,
        is_independent=se.is_independent,
        notes=None,
    )


class SignalNormalizer:
    """Converts a list of Evidence items into a normalized Signals object."""

    def __init__(self, radar_cfg: dict) -> None:
        self._cfg = radar_cfg
        self._saturation_clf = SaturationClassifier(radar_cfg)

    def normalize(self, evidence_list: list[Evidence], niche: str) -> Signals:
        signals = Signals()

        if not evidence_list:
            return signals

        # Independent source count (deduplicated by source_id)
        seen_source_ids: set[str] = set()
        independent_count = 0
        for ev in evidence_list:
            if ev.is_independent and ev.source_id not in seen_source_ids:
                independent_count += 1
                seen_source_ids.add(ev.source_id)

        signals.independent_source_count = independent_count
        signals.cross_source_confirmed = independent_count >= 2

        # Freshness — age of most recent evidence
        ages = [_age_hours(ev.observed_at) for ev in evidence_list]
        min_age_hours = min(ages) if ages else 9999
        signals.freshness_days = int(min_age_hours / 24)

        # YouTube signals
        yt_evidence = [ev for ev in evidence_list if ev.source_type == "youtube"]
        signals = self._apply_youtube_signals(signals, yt_evidence)

        # Trends / search signals
        trend_evidence = [ev for ev in evidence_list if ev.source_type == "trends"]
        signals = self._apply_trend_signals(signals, trend_evidence)

        # Saturation classification
        signals.saturation_state = self._saturation_clf.classify(evidence_list, niche)

        # Packaging potential (from any evidence metadata)
        signals.audience_relevance = "high" if niche == "ai_tech" else "medium"
        signals.production_feasibility = "high"  # default; can be lowered
        signals.monetization_strength = "high" if niche == "ai_tech" else "medium"
        signals.title_potential = "good"
        signals.thumbnail_potential = "good"

        return signals

    def _apply_youtube_signals(self, signals: Signals, yt_ev: list[Evidence]) -> Signals:
        if not yt_ev:
            return signals

        multipliers: list[float] = []
        breakout_found = False
        recurrence = 0
        seen_channels: set[str] = set()

        breakout_threshold = self._cfg["stage1"]["youtube_breakout_multiplier"]

        for ev in yt_ev:
            p = ev.observed_value
            if not isinstance(p, dict):
                continue

            rel_perf = p.get("relative_performance", 0.0)
            multipliers.append(rel_perf)

            ch_id = p.get("channel_id", ev.source_id)
            if ch_id not in seen_channels:
                recurrence += 1
                seen_channels.add(ch_id)

            if rel_perf >= breakout_threshold:
                breakout_found = True

        signals.youtube_breakout = breakout_found
        if multipliers:
            signals.channel_relative_multiplier = round(max(multipliers), 2)
        signals.topic_recurrence_count = recurrence

        # Infer momentum from YouTube signals
        if breakout_found and recurrence >= 2:
            signals.momentum = MomentumState.ACCELERATING
        elif breakout_found or recurrence >= 1:
            signals.momentum = MomentumState.RISING
        else:
            signals.momentum = MomentumState.STABLE

        return signals

    def _apply_trend_signals(self, signals: Signals, trend_ev: list[Evidence]) -> Signals:
        if not trend_ev:
            return signals

        directions: list[str] = []
        accelerations: list[float] = []

        for ev in trend_ev:
            p = ev.observed_value
            if not isinstance(p, dict):
                continue
            directions.append(p.get("trend_direction", "stable"))
            accel = p.get("acceleration_ratio", 0.0)
            accelerations.append(accel)

        rising_count = directions.count("rising")
        avg_accel = sum(accelerations) / len(accelerations) if accelerations else 0.0

        if rising_count > 0 and avg_accel > 0.5:
            momentum = MomentumState.ACCELERATING
        elif rising_count > 0:
            momentum = MomentumState.RISING
        elif "falling" in directions:
            momentum = MomentumState.DECLINING
        else:
            momentum = MomentumState.STABLE

        # Trend momentum overrides YouTube momentum only if stronger
        _strength = {
            MomentumState.ACCELERATING: 3,
            MomentumState.RISING: 2,
            MomentumState.STABLE: 1,
            MomentumState.DECLINING: 0,
            MomentumState.UNKNOWN: -1,
        }
        if _strength.get(momentum, 0) > _strength.get(signals.momentum, 0):
            signals.momentum = momentum

        return signals
