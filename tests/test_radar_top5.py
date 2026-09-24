"""Tests for Top5Selector — max 5, human approval required, ranking."""

from datetime import datetime, timezone, timedelta
import pytest

from delta.config import radar_config, reload_all
from delta.models.radar import (
    DailyTop5, Evidence, LifecycleState, MomentumState, RadarCandidate,
    SaturationState, Signals,
)
from delta.radar.top5 import Top5Selector


@pytest.fixture(autouse=True)
def clear_cache():
    reload_all()
    yield
    reload_all()


def _cfg():
    return radar_config()["radar"]


def _validated_candidate(
    topic: str = "Topic",
    opportunity_score: float = 0.70,
    confidence_score: float = 0.65,
    niche: str = "ai_tech",
) -> RadarCandidate:
    c = RadarCandidate(topic=topic, niche=niche)
    c.lifecycle = LifecycleState.VALIDATED
    c.opportunity_score = opportunity_score
    c.confidence_score = confidence_score
    c.saturation_state = SaturationState.EMERGING
    c.momentum_state = MomentumState.RISING
    c.signals = Signals(
        momentum=MomentumState.RISING,
        freshness_days=1,
        independent_source_count=2,
        cross_source_confirmed=True,
        saturation_state=SaturationState.EMERGING,
        audience_relevance="high",
        monetization_strength="high",
        title_potential="good",
        thumbnail_potential="good",
    )
    return c


def test_top5_cannot_exceed_five():
    selector = Top5Selector(_cfg())
    candidates = [
        _validated_candidate(f"Topic {i}", opportunity_score=0.80 - i * 0.01)
        for i in range(10)
    ]
    result = selector.select(candidates)
    assert len(result.reports) <= 5


def test_top5_raises_if_constructed_with_more_than_five():
    from delta.models.radar import OpportunityReport
    with pytest.raises(ValueError):
        DailyTop5(reports=[
            OpportunityReport(
                topic=f"T{i}", niche="ai_tech",
                lifecycle=LifecycleState.HUMAN_APPROVAL,
                opportunity_score=0.7, confidence_score=0.6,
                momentum_state=MomentumState.RISING,
                saturation_state=SaturationState.EMERGING,
                why_now="x", strongest_evidence="x", main_risk="x",
                recommended_formats=["SHORT"], suggested_angle="x",
            )
            for i in range(6)  # 6 > 5
        ])


def test_human_approval_always_pending():
    selector = Top5Selector(_cfg())
    candidates = [_validated_candidate(f"Topic {i}") for i in range(3)]
    result = selector.select(candidates)
    for report in result.reports:
        assert report.human_approved is None, (
            "Reports must start as pending human approval"
        )


def test_all_pending_approval_check():
    selector = Top5Selector(_cfg())
    candidates = [_validated_candidate(f"Topic {i}") for i in range(2)]
    result = selector.select(candidates)
    assert result.all_pending_approval()


def test_watch_candidates_excluded_from_top5():
    selector = Top5Selector(_cfg())
    c = _validated_candidate()
    c.lifecycle = LifecycleState.WATCH  # not VALIDATED
    result = selector.select([c])
    assert len(result.reports) == 0


def test_below_min_score_excluded():
    selector = Top5Selector(_cfg())
    c = _validated_candidate(opportunity_score=0.10, confidence_score=0.10)
    result = selector.select([c])
    assert len(result.reports) == 0


def test_ranking_by_opportunity_score():
    selector = Top5Selector(_cfg())
    candidates = [
        _validated_candidate("Low", opportunity_score=0.50, confidence_score=0.60),
        _validated_candidate("High", opportunity_score=0.90, confidence_score=0.80),
        _validated_candidate("Mid", opportunity_score=0.70, confidence_score=0.65),
    ]
    result = selector.select(candidates)
    scores = [r.opportunity_score for r in result.reports]
    assert scores == sorted(scores, reverse=True)


def test_candidates_lifecycle_set_to_human_approval():
    selector = Top5Selector(_cfg())
    c = _validated_candidate(opportunity_score=0.80)
    result = selector.select([c])
    if result.reports:
        assert result.reports[0].lifecycle == LifecycleState.HUMAN_APPROVAL


def test_empty_candidate_list_returns_empty_top5():
    selector = Top5Selector(_cfg())
    result = selector.select([])
    assert len(result.reports) == 0
    assert result.candidates_evaluated == 0


def test_report_has_all_required_fields():
    selector = Top5Selector(_cfg())
    c = _validated_candidate("Test Topic", opportunity_score=0.75, confidence_score=0.65)
    result = selector.select([c])
    assert len(result.reports) == 1
    r = result.reports[0]
    assert r.topic == "Test Topic"
    assert r.opportunity_score > 0
    assert r.confidence_score > 0
    assert r.recommended_formats
    assert r.suggested_angle
    assert r.why_now
    d = r.to_dict()
    required_keys = [
        "topic", "niche", "lifecycle", "opportunity_score", "confidence_score",
        "momentum", "saturation", "why_now", "strongest_evidence", "main_risk",
        "recommended_formats", "suggested_angle", "human_approved",
    ]
    for key in required_keys:
        assert key in d, f"Missing key in report dict: {key}"
