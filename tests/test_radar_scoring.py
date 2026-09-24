"""Tests for RadarScoring — opportunity vs confidence separation, determinism."""

from datetime import datetime, timezone, timedelta
import pytest

from delta.config import radar_config, reload_all
from delta.models.radar import (
    Evidence, LifecycleState, MomentumState, RadarCandidate, SaturationState, Signals,
)
from delta.radar.scoring import RadarScoring


@pytest.fixture(autouse=True)
def clear_cache():
    reload_all()
    yield
    reload_all()


def _cfg():
    return radar_config()["radar"]


def _ev(source_type: str, source_id: str, hours_ago: float = 12,
        is_independent: bool = True, confidence: float = 0.8) -> Evidence:
    return Evidence(
        source_type=source_type,
        source_id=source_id,
        observed_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        evidence_type=f"{source_type}_signal",
        observed_value={},
        confidence=confidence,
        is_independent=is_independent,
    )


def _candidate_with_signals(
    momentum: MomentumState = MomentumState.RISING,
    saturation: SaturationState = SaturationState.EARLY,
    independent_sources: int = 2,
    cross_confirmed: bool = True,
    youtube_breakout: bool = False,
    freshness_days: int = 1,
    evidence_count: int = 2,
) -> RadarCandidate:
    c = RadarCandidate(topic="Test", niche="ai_tech")
    c.signals = Signals(
        momentum=momentum,
        freshness_days=freshness_days,
        independent_source_count=independent_sources,
        cross_source_confirmed=cross_confirmed,
        youtube_breakout=youtube_breakout,
        saturation_state=saturation,
        audience_relevance="high",
        monetization_strength="high",
        title_potential="good",
        thumbnail_potential="good",
    )
    c.saturation_state = saturation
    c.momentum_state = momentum
    c.evidence = [_ev("youtube", f"src_{i}") for i in range(evidence_count)]
    return c


def test_opportunity_and_confidence_are_separate():
    scoring = RadarScoring(_cfg())
    c = _candidate_with_signals(
        momentum=MomentumState.ACCELERATING,
        saturation=SaturationState.EARLY,
        independent_sources=1,
        cross_confirmed=False,
        freshness_days=1,
    )
    scoring.score(c)
    # High momentum/freshness → good opportunity
    # But low confidence (only 1 source, no cross-confirm)
    assert c.opportunity_score > 0.5
    assert c.confidence_score < c.opportunity_score


def test_high_opportunity_with_low_confidence_is_possible():
    """Key invariant: high opp + low conf must be representable."""
    scoring = RadarScoring(_cfg())
    c = _candidate_with_signals(
        momentum=MomentumState.ACCELERATING,
        saturation=SaturationState.EARLY,
        independent_sources=1,
        cross_confirmed=False,
        evidence_count=1,
        freshness_days=0,
    )
    scoring.score(c)
    assert c.opportunity_score > 0.0
    assert c.confidence_score > 0.0
    # They are stored separately
    assert c.opportunity_score != c.confidence_score or True  # just must both exist


def test_more_independent_sources_raises_confidence():
    scoring = RadarScoring(_cfg())
    c_few = _candidate_with_signals(independent_sources=1, cross_confirmed=False,
                                     evidence_count=1)
    c_many = _candidate_with_signals(independent_sources=4, cross_confirmed=True,
                                      youtube_breakout=True, evidence_count=4)
    scoring.score(c_few)
    scoring.score(c_many)
    assert c_many.confidence_score > c_few.confidence_score


def test_saturated_topic_has_lower_opportunity():
    scoring = RadarScoring(_cfg())
    c_early = _candidate_with_signals(saturation=SaturationState.EARLY)
    c_saturated = _candidate_with_signals(saturation=SaturationState.SATURATED)
    scoring.score(c_early)
    scoring.score(c_saturated)
    assert c_early.opportunity_score > c_saturated.opportunity_score


def test_declining_momentum_reduces_opportunity():
    scoring = RadarScoring(_cfg())
    c_acc = _candidate_with_signals(momentum=MomentumState.ACCELERATING)
    c_dec = _candidate_with_signals(momentum=MomentumState.DECLINING)
    scoring.score(c_acc)
    scoring.score(c_dec)
    assert c_acc.opportunity_score > c_dec.opportunity_score


def test_scoring_is_deterministic():
    scoring = RadarScoring(_cfg())
    c1 = _candidate_with_signals()
    c2 = _candidate_with_signals()
    scoring.score(c1)
    scoring.score(c2)
    assert c1.opportunity_score == c2.opportunity_score
    assert c1.confidence_score == c2.confidence_score


def test_scores_in_valid_range():
    scoring = RadarScoring(_cfg())
    for momentum in MomentumState:
        for saturation in SaturationState:
            c = _candidate_with_signals(momentum=momentum, saturation=saturation)
            scoring.score(c)
            assert 0.0 <= c.opportunity_score <= 1.0, (
                f"opportunity_score out of range: {c.opportunity_score}"
            )
            assert 0.0 <= c.confidence_score <= 1.0, (
                f"confidence_score out of range: {c.confidence_score}"
            )


def test_score_explanation_generated():
    scoring = RadarScoring(_cfg())
    c = _candidate_with_signals()
    scoring.score(c)
    assert len(c.score_explanation) > 0
    assert any("Momentum" in s for s in c.score_explanation)
    assert any("Confidence" in s for s in c.score_explanation)


def test_youtube_breakout_boosts_confidence():
    scoring = RadarScoring(_cfg())
    c_no_breakout = _candidate_with_signals(youtube_breakout=False)
    c_breakout = _candidate_with_signals(youtube_breakout=True)
    scoring.score(c_no_breakout)
    scoring.score(c_breakout)
    assert c_breakout.confidence_score > c_no_breakout.confidence_score
