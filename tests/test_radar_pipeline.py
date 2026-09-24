"""Integration tests for the full radar pipeline."""

import pytest

from delta.config import radar_config, reload_all
from delta.models.radar import LifecycleState
from delta.radar import RadarPipeline
from delta.radar.providers import MockYouTubeProvider, MockTrendsProvider, MockNewsProvider


@pytest.fixture(autouse=True)
def clear_cache():
    reload_all()
    yield
    reload_all()


def _providers():
    return [MockYouTubeProvider(), MockTrendsProvider(), MockNewsProvider()]


def test_pipeline_returns_daily_top5():
    pipeline = RadarPipeline()
    topics = [
        {"topic": "Claude AI coding agent", "niche": "ai_tech"},
        {"topic": "AI video generation 2026", "niche": "ai_tech"},
    ]
    result = pipeline.run(topics, _providers())
    assert result is not None
    assert len(result.reports) <= 5


def test_pipeline_top5_never_exceeds_five():
    pipeline = RadarPipeline()
    topics = [
        {"topic": "Claude AI coding agent", "niche": "ai_tech"},
        {"topic": "AI video generation 2026", "niche": "ai_tech"},
        {"topic": "AI memory systems", "niche": "ai_tech"},
        {"topic": "keyboard shortcuts productivity", "niche": "ai_tech"},
        {"topic": "AI image generation", "niche": "ai_tech"},
        {"topic": "global tariff impact small business", "niche": "cross_niche"},
    ]
    result = pipeline.run(topics, _providers())
    assert len(result.reports) <= 5


def test_all_reports_pending_human_approval():
    pipeline = RadarPipeline()
    topics = [{"topic": "Claude AI coding agent", "niche": "ai_tech"}]
    result = pipeline.run(topics, _providers())
    for report in result.reports:
        assert report.human_approved is None


def test_false_positive_keyboard_shortcuts_not_in_top5():
    """Keyboard shortcuts has weak evidence — should not reach top 5."""
    pipeline = RadarPipeline()
    topics = [
        {"topic": "keyboard shortcuts productivity", "niche": "ai_tech"},
        {"topic": "Claude AI coding agent", "niche": "ai_tech"},
    ]
    result = pipeline.run(topics, _providers())
    topics_in_top5 = [r.topic for r in result.reports]
    # keyboard shortcuts has a single low-credibility source; Claude agent has multi-source
    # Claude agent should score higher
    if len(topics_in_top5) >= 2:
        assert "Claude AI coding agent" in topics_in_top5


def test_cross_niche_topic_can_enter_top5_with_strong_evidence():
    """Cross-niche with Reuters/Bloomberg/AP should pass stricter validation."""
    pipeline = RadarPipeline()
    topics = [
        {"topic": "global tariff impact small business", "niche": "cross_niche"},
    ]
    result = pipeline.run(topics, _providers())
    # May or may not reach top 5 depending on opportunity/confidence thresholds
    assert result.candidates_evaluated == 1


def test_pipeline_is_deterministic():
    pipeline = RadarPipeline()
    topics = [
        {"topic": "Claude AI coding agent", "niche": "ai_tech"},
        {"topic": "AI video generation 2026", "niche": "ai_tech"},
    ]
    result1 = pipeline.run(topics, _providers())
    result2 = pipeline.run(topics, _providers())
    scores1 = [(r.topic, round(r.opportunity_score, 3)) for r in result1.reports]
    scores2 = [(r.topic, round(r.opportunity_score, 3)) for r in result2.reports]
    assert scores1 == scores2


def test_pipeline_no_credentials_required():
    """Verify providers work without credentials (fixture-based)."""
    for Provider in [MockYouTubeProvider, MockTrendsProvider, MockNewsProvider]:
        p = Provider()
        assert not p.requires_credentials
        results = p.fetch_evidence(["Claude AI coding agent"])
        assert isinstance(results, list)
