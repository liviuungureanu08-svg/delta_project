"""Tests for the Opportunity Engine."""

import pytest
from delta.config import reload_all
from delta.engine import OpportunityEngine
from delta.models.topic import CompetitionIndicators, DemandIndicators, TopicCandidate


@pytest.fixture(autouse=True)
def clear_cache():
    reload_all()
    yield
    reload_all()


def _make_candidate(**kwargs) -> TopicCandidate:
    defaults = dict(
        topic="Test Topic",
        source="test",
        audience_relevance="high",
        freshness="fresh",
        demand=DemandIndicators(search_trend="rising"),
        competition=CompetitionIndicators(saturation="low"),
        monetization_potential="high",
        title_potential="excellent",
        thumbnail_potential="good",
        available_evidence=["e1", "e2"],
    )
    defaults.update(kwargs)
    return TopicCandidate(**defaults)


def test_score_returns_value_in_range():
    engine = OpportunityEngine()
    c = _make_candidate()
    engine.score(c)
    assert 0.0 <= c.opportunity_score <= 1.0
    assert 0.0 < c.confidence <= 1.0


def test_strong_signals_score_high():
    engine = OpportunityEngine()
    c = _make_candidate(
        audience_relevance="high",
        freshness="very fresh",
        demand=DemandIndicators(search_trend="rising"),
        competition=CompetitionIndicators(saturation="low"),
        monetization_potential="high",
        title_potential="excellent",
        thumbnail_potential="excellent",
        available_evidence=["a", "b", "c", "d", "e"],
    )
    engine.score(c)
    assert c.opportunity_score >= 0.75


def test_weak_signals_score_low():
    engine = OpportunityEngine()
    c = _make_candidate(
        audience_relevance="low",
        freshness="dated",
        demand=DemandIndicators(search_trend="falling"),
        competition=CompetitionIndicators(saturation="high"),
        monetization_potential="low",
        title_potential="low",
        thumbnail_potential="low",
        available_evidence=[],
    )
    engine.score(c)
    assert c.opportunity_score < 0.4


def test_more_evidence_increases_confidence():
    engine = OpportunityEngine()
    c_few = _make_candidate(available_evidence=["one"])
    c_many = _make_candidate(available_evidence=["a", "b", "c", "d", "e", "f"])
    engine.score(c_few)
    engine.score(c_many)
    assert c_many.confidence >= c_few.confidence


def test_formats_recommended_for_high_score():
    engine = OpportunityEngine()
    c = _make_candidate(
        freshness="very fresh",
        demand=DemandIndicators(search_trend="rising"),
        competition=CompetitionIndicators(saturation="low"),
        available_evidence=["a", "b", "c", "d", "e"],
    )
    engine.score(c)
    assert "SHORT" in c.recommended_formats
    assert "UTILITY_LONG_FORM" in c.recommended_formats


def test_no_formats_for_very_low_score():
    engine = OpportunityEngine()
    c = _make_candidate(
        audience_relevance="low",
        freshness="dated",
        demand=DemandIndicators(search_trend="falling"),
        competition=CompetitionIndicators(saturation="high"),
        monetization_potential="low",
        title_potential="low",
        thumbnail_potential="low",
        available_evidence=[],
    )
    engine.score(c)
    assert len(c.recommended_formats) == 0


def test_is_worth_proceeding():
    engine = OpportunityEngine()
    good = _make_candidate()
    engine.score(good)
    if good.opportunity_score >= 0.55:
        assert engine.is_worth_proceeding(good)
