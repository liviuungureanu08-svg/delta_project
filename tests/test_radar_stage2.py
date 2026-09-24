"""Tests for Stage 2 Validation — false-positive reduction."""

from datetime import datetime, timezone, timedelta
import pytest

from delta.config import radar_config, reload_all
from delta.models.radar import Evidence, LifecycleState, RadarCandidate
from delta.radar.scoring import RadarScoring
from delta.radar.stage1 import Stage1Discovery
from delta.radar.stage2 import Stage2Validation


@pytest.fixture(autouse=True)
def clear_cache():
    reload_all()
    yield
    reload_all()


def _cfg():
    return radar_config()["radar"]


def _ev(source_type: str, source_id: str, payload: dict = None,
        confidence: float = 0.8, is_independent: bool = True,
        hours_ago: float = 12) -> Evidence:
    return Evidence(
        source_type=source_type,
        source_id=source_id,
        observed_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        evidence_type=f"{source_type}_signal",
        observed_value=payload or {},
        confidence=confidence,
        is_independent=is_independent,
    )


def _watch_candidate(topic: str = "Test", niche: str = "ai_tech",
                     evidence: list = None) -> RadarCandidate:
    c = RadarCandidate(topic=topic, niche=niche, evidence=evidence or [])
    c.lifecycle = LifecycleState.WATCH
    c.opportunity_score = 0.65  # above ai_tech threshold
    return c


def test_watch_with_sufficient_independent_sources_validates():
    cfg = _cfg()
    stage1 = Stage1Discovery(cfg)
    stage2 = Stage2Validation(cfg)
    scoring = RadarScoring(cfg)
    c = RadarCandidate(topic="Test", niche="ai_tech", evidence=[
        _ev("youtube", "vid_1", {"channel_id": "ch_a", "relative_performance": 3.0,
             "channel_upload_frequency_days": 7, "channel_baseline_views": 10000}),
        _ev("trends", "t1", {"trend_direction": "rising", "acceleration_ratio": 0.8,
             "relative_interest_now": 80, "relative_interest_7d_ago": 40}),
        _ev("news", "art_1", {"source_credibility": "high"}),
    ])
    # Must run stage1 first to normalize signals; stage2 checks opportunity_score
    stage1.process(c)
    scoring.score(c)
    stage2.process(c)
    assert c.lifecycle == LifecycleState.VALIDATED


def test_single_source_stays_watch_for_ai_tech():
    cfg = _cfg()
    stage2 = Stage2Validation(cfg)
    # ai_tech requires 2 independent sources for validation
    c = _watch_candidate(evidence=[
        _ev("youtube", "vid_1", {"channel_id": "ch_a", "relative_performance": 4.0,
             "channel_upload_frequency_days": 7, "channel_baseline_views": 10000}),
    ])
    stage2.process(c)
    assert c.lifecycle == LifecycleState.WATCH


def test_cross_niche_requires_more_sources():
    cfg = _cfg()
    stage2 = Stage2Validation(cfg)
    # cross_niche requires 3 independent sources
    c = _watch_candidate(niche="cross_niche", evidence=[
        _ev("youtube", "vid_1", {"channel_id": "ch_a", "relative_performance": 5.0,
             "channel_upload_frequency_days": 7, "channel_baseline_views": 30000}),
        _ev("news", "art_1", {"source_credibility": "high"}, confidence=0.9),
    ])
    c.opportunity_score = 0.70
    stage2.process(c)
    # Only 2 sources, but cross_niche needs 3 → stays WATCH
    assert c.lifecycle == LifecycleState.WATCH


def test_large_channel_single_spike_is_false_positive():
    cfg = _cfg()
    stage2 = Stage2Validation(cfg)
    # Single large channel (baseline > 100k) performing at normal level
    c = _watch_candidate(evidence=[
        _ev("youtube", "vid_1", {
            "channel_id": "ch_mega",
            "relative_performance": 1.1,   # normal performance for this channel
            "channel_baseline_views": 450_000,  # > large_channel_baseline_threshold
            "channel_upload_frequency_days": 3,
        }),
    ])
    stage2.process(c)
    assert c.lifecycle == LifecycleState.WATCH
    assert c.main_risk is not None


def test_stale_evidence_stays_watch():
    cfg = _cfg()
    stage2 = Stage2Validation(cfg)
    # Evidence older than max_evidence_age_hours doesn't count for ai_tech (72h)
    c = _watch_candidate(evidence=[
        _ev("youtube", "vid_1", {"channel_id": "ch_a", "relative_performance": 4.0,
             "channel_upload_frequency_days": 7, "channel_baseline_views": 10000},
            hours_ago=100),  # stale for ai_tech (> 72h)
        _ev("news", "art_1", {"source_credibility": "high"}, hours_ago=100),
    ])
    stage2.process(c)
    assert c.lifecycle == LifecycleState.WATCH


def test_low_confidence_evidence_blocked():
    cfg = _cfg()
    stage2 = Stage2Validation(cfg)
    # Evidence with very low confidence
    c = _watch_candidate(evidence=[
        _ev("news", "art_1", {"source_credibility": "low"}, confidence=0.20),
        _ev("news", "art_2", {"source_credibility": "low"}, confidence=0.20),
        _ev("news", "art_3", {"source_credibility": "low"}, confidence=0.20),
    ])
    stage2.process(c)
    # Average confidence 0.20 < 0.55 min → stays WATCH
    assert c.lifecycle == LifecycleState.WATCH


def test_non_watch_candidate_not_modified():
    cfg = _cfg()
    stage2 = Stage2Validation(cfg)
    c = _watch_candidate()
    c.lifecycle = LifecycleState.DISCOVERED
    stage2.process(c)
    assert c.lifecycle == LifecycleState.DISCOVERED


def test_validated_candidate_has_no_main_risk():
    cfg = _cfg()
    stage2 = Stage2Validation(cfg)
    c = _watch_candidate(evidence=[
        _ev("youtube", "vid_1", {"channel_id": "ch_a", "relative_performance": 3.0,
             "channel_upload_frequency_days": 7, "channel_baseline_views": 10000}),
        _ev("trends", "t1", {"trend_direction": "rising", "acceleration_ratio": 0.8,
             "relative_interest_now": 80, "relative_interest_7d_ago": 40}),
        _ev("news", "art_1", {"source_credibility": "high"}),
    ])
    stage2.process(c)
    if c.lifecycle == LifecycleState.VALIDATED:
        assert c.main_risk is None
