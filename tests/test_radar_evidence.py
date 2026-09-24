"""Tests for Evidence provenance model and provider output."""

from datetime import datetime, timezone
import pytest

from delta.models.radar import Evidence, LifecycleState, RadarCandidate
from delta.radar.providers.youtube import MockYouTubeProvider
from delta.radar.providers.trends import MockTrendsProvider
from delta.radar.providers.news import MockNewsProvider
from delta.radar.signals import evidence_from_source


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_evidence_has_required_fields():
    ev = Evidence(
        source_type="youtube",
        source_id="vid_001",
        observed_at=_utc_now(),
        evidence_type="youtube_video",
        observed_value={"views": 50000},
        confidence=0.8,
        is_independent=True,
    )
    assert ev.source_type == "youtube"
    assert ev.is_independent is True
    assert 0.0 <= ev.confidence <= 1.0


def test_youtube_provider_returns_evidence():
    provider = MockYouTubeProvider()
    results = provider.fetch_evidence(["Claude AI coding agent"])
    assert len(results) > 0
    for ev in results:
        assert ev.source_type == "youtube"
        assert ev.evidence_type == "youtube_video"
        assert "relative_performance" in ev.payload


def test_trends_provider_returns_evidence():
    provider = MockTrendsProvider()
    results = provider.fetch_evidence(["Claude AI coding agent"])
    assert len(results) > 0
    for ev in results:
        assert ev.source_type == "trends"
        assert "trend_direction" in ev.payload
        assert "acceleration_ratio" in ev.payload


def test_news_provider_returns_evidence():
    provider = MockNewsProvider()
    results = provider.fetch_evidence(["Claude AI coding agent"])
    assert len(results) > 0
    for ev in results:
        assert ev.source_type == "news"
        assert "source_credibility" in ev.payload


def test_providers_return_empty_for_unknown_topic():
    for Provider in [MockYouTubeProvider, MockTrendsProvider, MockNewsProvider]:
        provider = Provider()
        results = provider.fetch_evidence(["xyz_no_match_topic_12345"])
        assert results == []


def test_evidence_from_source_conversion():
    provider = MockYouTubeProvider()
    source_evs = provider.fetch_evidence(["Claude AI coding agent"])
    assert source_evs
    ev = evidence_from_source(source_evs[0])
    assert isinstance(ev, Evidence)
    assert ev.source_type == "youtube"
    assert ev.confidence > 0.0


def test_evidence_independence_flag():
    provider = MockYouTubeProvider()
    results = provider.fetch_evidence(["Claude AI coding agent"])
    # All mock YouTube evidence is marked independent
    assert all(r.is_independent for r in results)


def test_evidence_confidence_in_range():
    for Provider in [MockYouTubeProvider, MockTrendsProvider, MockNewsProvider]:
        provider = Provider()
        results = provider.fetch_evidence(["AI video generation 2026"])
        for ev in results:
            assert 0.0 <= ev.base_confidence <= 1.0, (
                f"Confidence out of range: {ev.base_confidence}"
            )


def test_low_credibility_news_has_lower_confidence():
    provider = MockNewsProvider()
    # "keyboard shortcuts productivity" has a low-credibility source
    results = provider.fetch_evidence(["keyboard shortcuts productivity"])
    low_cred = [r for r in results if r.payload.get("source_credibility") == "low"]
    high_cred = [r for r in results if r.payload.get("source_credibility") == "high"]
    if low_cred and high_cred:
        assert low_cred[0].base_confidence < high_cred[0].base_confidence
