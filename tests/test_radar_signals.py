"""Tests for signal normalization."""

from datetime import datetime, timezone, timedelta
import pytest

from delta.config import radar_config, reload_all
from delta.models.radar import Evidence, MomentumState, SaturationState
from delta.radar.signals import SignalNormalizer


@pytest.fixture(autouse=True)
def clear_cache():
    reload_all()
    yield
    reload_all()


def _ev(source_type: str, source_id: str, payload: dict, confidence: float = 0.8,
        is_independent: bool = True, hours_ago: float = 12) -> Evidence:
    return Evidence(
        source_type=source_type,
        source_id=source_id,
        observed_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        evidence_type=f"{source_type}_signal",
        observed_value=payload,
        confidence=confidence,
        is_independent=is_independent,
    )


def _cfg():
    return radar_config()["radar"]


def test_empty_evidence_returns_default_signals():
    norm = SignalNormalizer(_cfg())
    signals = norm.normalize([], "ai_tech")
    assert signals.independent_source_count == 0
    assert signals.cross_source_confirmed is False
    assert signals.momentum == MomentumState.UNKNOWN


def test_independent_source_count_deduplicates():
    norm = SignalNormalizer(_cfg())
    ev1 = _ev("youtube", "ch_a", {"channel_id": "ch_a", "relative_performance": 2.0,
               "channel_upload_frequency_days": 7, "channel_baseline_views": 10000})
    ev2 = _ev("youtube", "ch_a", {"channel_id": "ch_a", "relative_performance": 2.0,
               "channel_upload_frequency_days": 7, "channel_baseline_views": 10000})
    signals = norm.normalize([ev1, ev2], "ai_tech")
    # Same source_id: only 1 independent source despite 2 evidence items
    assert signals.independent_source_count == 1


def test_cross_source_confirmed_requires_two_independent():
    norm = SignalNormalizer(_cfg())
    ev1 = _ev("youtube", "vid_1", {"channel_id": "ch_a", "relative_performance": 3.0,
               "channel_upload_frequency_days": 7, "channel_baseline_views": 10000})
    ev2 = _ev("trends", "trends_1", {"trend_direction": "rising", "acceleration_ratio": 0.8,
               "relative_interest_now": 80, "relative_interest_7d_ago": 40})
    signals = norm.normalize([ev1, ev2], "ai_tech")
    assert signals.cross_source_confirmed is True


def test_single_source_not_cross_confirmed():
    norm = SignalNormalizer(_cfg())
    ev1 = _ev("youtube", "vid_1", {"channel_id": "ch_a", "relative_performance": 5.0,
               "channel_upload_frequency_days": 7, "channel_baseline_views": 10000})
    signals = norm.normalize([ev1], "ai_tech")
    assert signals.cross_source_confirmed is False


def test_youtube_breakout_detected():
    norm = SignalNormalizer(_cfg())
    ev = _ev("youtube", "vid_1", {
        "channel_id": "ch_a",
        "relative_performance": 5.0,  # > breakout_multiplier (2.5)
        "channel_upload_frequency_days": 7,
        "channel_baseline_views": 10000,
    })
    signals = norm.normalize([ev], "ai_tech")
    assert signals.youtube_breakout is True


def test_below_breakout_threshold_not_flagged():
    norm = SignalNormalizer(_cfg())
    ev = _ev("youtube", "vid_1", {
        "channel_id": "ch_a",
        "relative_performance": 1.2,  # < breakout_multiplier
        "channel_upload_frequency_days": 7,
        "channel_baseline_views": 10000,
    })
    signals = norm.normalize([ev], "ai_tech")
    assert signals.youtube_breakout is False


def test_accelerating_momentum_from_rising_trend_and_high_acceleration():
    norm = SignalNormalizer(_cfg())
    ev = _ev("trends", "t1", {
        "trend_direction": "rising",
        "acceleration_ratio": 1.0,  # > 0.5
        "relative_interest_now": 80,
        "relative_interest_7d_ago": 30,
    })
    signals = norm.normalize([ev], "ai_tech")
    assert signals.momentum == MomentumState.ACCELERATING


def test_freshness_days_computed():
    norm = SignalNormalizer(_cfg())
    ev = _ev("youtube", "vid_1", {
        "channel_id": "ch_a", "relative_performance": 2.0,
        "channel_upload_frequency_days": 7, "channel_baseline_views": 10000,
    }, hours_ago=48)
    signals = norm.normalize([ev], "ai_tech")
    # 48 hours = 2 days
    assert signals.freshness_days == 2


def test_stale_evidence_shows_higher_freshness_days():
    norm = SignalNormalizer(_cfg())
    ev = _ev("youtube", "vid_1", {
        "channel_id": "ch_a", "relative_performance": 2.0,
        "channel_upload_frequency_days": 7, "channel_baseline_views": 10000,
    }, hours_ago=120)
    signals = norm.normalize([ev], "ai_tech")
    assert signals.freshness_days == 5
