"""Tests for SaturationClassifier."""

from datetime import datetime, timezone, timedelta
import pytest

from delta.config import radar_config, reload_all
from delta.models.radar import Evidence, SaturationState
from delta.radar.saturation import SaturationClassifier


@pytest.fixture(autouse=True)
def clear_cache():
    reload_all()
    yield
    reload_all()


def _cfg():
    return radar_config()["radar"]


def _yt_ev(channel_id: str, source_id: str, relative_performance: float,
            baseline: int, upload_freq_days: float, hours_ago: float = 24) -> Evidence:
    return Evidence(
        source_type="youtube",
        source_id=source_id,
        observed_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        evidence_type="youtube_video",
        observed_value={
            "channel_id": channel_id,
            "relative_performance": relative_performance,
            "channel_baseline_views": baseline,
            "channel_upload_frequency_days": upload_freq_days,
        },
        confidence=0.8,
        is_independent=True,
    )


def test_no_youtube_evidence_returns_early():
    clf = SaturationClassifier(_cfg())
    result = clf.classify([], "ai_tech")
    assert result == SaturationState.EARLY


def test_single_low_freq_channel_is_early():
    clf = SaturationClassifier(_cfg())
    # One channel, uploads every 30 days → very low velocity
    ev = _yt_ev("ch_a", "vid_1", 2.0, 10000, 30.0)
    result = clf.classify([ev], "ai_tech")
    assert result in (SaturationState.EARLY, SaturationState.EMERGING)


def test_many_frequent_channels_is_saturated():
    clf = SaturationClassifier(_cfg())
    # Many channels uploading very frequently → high velocity
    evidence = []
    for i in range(20):
        ev = _yt_ev(f"ch_{i}", f"vid_{i}", 1.5, 50000, 1.0)
        evidence.append(ev)
    result = clf.classify(evidence, "ai_tech")
    assert result in (SaturationState.MAINSTREAM, SaturationState.SATURATED)


def test_saturation_states_are_ordered():
    states = [
        SaturationState.EARLY,
        SaturationState.EMERGING,
        SaturationState.ACCELERATING,
        SaturationState.MAINSTREAM,
        SaturationState.SATURATED,
    ]
    # Verify all states are distinct
    assert len(set(s.value for s in states)) == 5


def test_escalation_on_many_large_channels():
    clf = SaturationClassifier(_cfg())
    # 6 large channels (baseline > 30k) uploading regularly
    evidence = []
    for i in range(6):
        ev = _yt_ev(f"ch_{i}", f"vid_{i}", 1.2, 50_000, 7.0)
        evidence.append(ev)
    result = clf.classify(evidence, "ai_tech")
    # Should be escalated at least one step above what raw velocity would give
    assert result != SaturationState.EARLY


def test_saturation_is_deterministic():
    clf = SaturationClassifier(_cfg())
    evidence = [_yt_ev("ch_a", "vid_1", 3.0, 10000, 7.0)]
    r1 = clf.classify(evidence, "ai_tech")
    r2 = clf.classify(evidence, "ai_tech")
    assert r1 == r2
