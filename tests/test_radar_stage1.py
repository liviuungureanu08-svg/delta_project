"""Tests for Stage 1 Sensitive Discovery."""

from datetime import datetime, timezone, timedelta
import pytest

from delta.config import radar_config, reload_all
from delta.models.radar import Evidence, LifecycleState, RadarCandidate
from delta.radar.stage1 import Stage1Discovery


@pytest.fixture(autouse=True)
def clear_cache():
    reload_all()
    yield
    reload_all()


def _cfg():
    return radar_config()["radar"]


def _fresh_ev(source_type: str, source_id: str, payload: dict = None,
              hours_ago: float = 12) -> Evidence:
    return Evidence(
        source_type=source_type,
        source_id=source_id,
        observed_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        evidence_type=f"{source_type}_signal",
        observed_value=payload or {},
        confidence=0.8,
        is_independent=True,
    )


def _candidate(topic: str = "Test Topic", niche: str = "ai_tech",
               evidence: list = None) -> RadarCandidate:
    return RadarCandidate(topic=topic, niche=niche, evidence=evidence or [])


def test_no_evidence_stays_discovered():
    stage1 = Stage1Discovery(_cfg())
    c = _candidate(evidence=[])
    stage1.process(c)
    assert c.lifecycle == LifecycleState.DISCOVERED


def test_one_independent_source_becomes_watch():
    stage1 = Stage1Discovery(_cfg())
    c = _candidate(evidence=[
        _fresh_ev("youtube", "vid_1", {
            "channel_id": "ch_a", "relative_performance": 2.0,
            "channel_upload_frequency_days": 7, "channel_baseline_views": 10000,
        })
    ])
    stage1.process(c)
    assert c.lifecycle == LifecycleState.WATCH


def test_stale_evidence_does_not_qualify():
    stage1 = Stage1Discovery(_cfg())
    # Evidence > 168 hours old is too stale for Stage 1 (max_evidence_age_hours=168)
    c = _candidate(evidence=[
        _fresh_ev("youtube", "vid_1", {
            "channel_id": "ch_a", "relative_performance": 5.0,
            "channel_upload_frequency_days": 7, "channel_baseline_views": 10000,
        }, hours_ago=200)  # stale
    ])
    stage1.process(c)
    assert c.lifecycle == LifecycleState.DISCOVERED


def test_stage1_sets_signals():
    stage1 = Stage1Discovery(_cfg())
    c = _candidate(evidence=[
        _fresh_ev("youtube", "vid_1", {
            "channel_id": "ch_a", "relative_performance": 3.5,
            "channel_upload_frequency_days": 7, "channel_baseline_views": 10000,
        })
    ])
    stage1.process(c)
    assert c.signals is not None
    assert c.momentum_state is not None
    assert c.saturation_state is not None


def test_stage1_favors_recall_with_minimal_evidence():
    """Stage 1 should enter WATCH with just 1 fresh independent source (recall-first)."""
    stage1 = Stage1Discovery(_cfg())
    c = _candidate(evidence=[
        _fresh_ev("news", "article_1", {"source_credibility": "high"}, hours_ago=6)
    ])
    stage1.process(c)
    # Should be WATCH (not REJECTED) — recall-first design
    assert c.lifecycle == LifecycleState.WATCH


def test_non_independent_evidence_does_not_count():
    stage1 = Stage1Discovery(_cfg())
    ev = _fresh_ev("youtube", "vid_1", {
        "channel_id": "ch_a", "relative_performance": 3.0,
        "channel_upload_frequency_days": 7, "channel_baseline_views": 10000,
    })
    ev.is_independent = False
    c = _candidate(evidence=[ev])
    stage1.process(c)
    assert c.lifecycle == LifecycleState.DISCOVERED
