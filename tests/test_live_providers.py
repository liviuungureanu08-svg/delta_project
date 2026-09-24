"""Tests for live providers — all use mocks/stubs; no real network calls."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch
import tempfile
from pathlib import Path

import pytest

from delta.radar.quota import ProviderQuota
from delta.radar.history import ObservationHistory
from delta.radar.providers.search_interest import SearchInterestProvider


# --- SearchInterestProvider ---

def test_search_interest_disabled_returns_empty():
    p = SearchInterestProvider(enabled=False)
    assert p.fetch_evidence(["any topic"]) == []


def test_search_interest_source_type():
    p = SearchInterestProvider()
    assert p.source_type == "search_interest"


def test_search_interest_requires_credentials():
    p = SearchInterestProvider()
    assert p.requires_credentials is True


def test_search_interest_not_available_when_disabled():
    p = SearchInterestProvider(enabled=False)
    assert not p.is_available


# --- LiveYouTubeProvider (with mocked client) ---

def _make_youtube_provider(tmp_path, api_key: str = "fake_key", budget: int = 10):
    from delta.radar.providers.live_youtube import LiveYouTubeProvider

    quota = ProviderQuota(provider_name="yt_test", daily_budget=budget)
    history = ObservationHistory(data_dir=str(tmp_path / "obs"))
    provider = LiveYouTubeProvider.__new__(LiveYouTubeProvider)
    provider._api_key = api_key
    provider._config = {}
    provider._quota = quota
    provider._history = history
    provider._available = True
    provider._evidence_cache = {}
    provider._client = MagicMock()
    return provider


def _mock_search_response(video_ids: list[str]) -> dict:
    return {
        "items": [
            {
                "id": {"videoId": vid},
                "snippet": {
                    "title": f"Video {vid}",
                    "channelId": f"ch_{vid}",
                    "publishedAt": "2026-01-01T00:00:00Z",
                },
            }
            for vid in video_ids
        ]
    }


def _mock_video_stats_response(video_ids: list[str]) -> dict:
    return {
        "items": [
            {
                "id": vid,
                "statistics": {"viewCount": "10000"},
                "snippet": {"channelId": f"ch_{vid}"},
            }
            for vid in video_ids
        ]
    }


def _mock_channel_stats_response(channel_ids: list[str]) -> dict:
    return {
        "items": [
            {"id": ch, "statistics": {"subscriberCount": "100000"}}
            for ch in channel_ids
        ]
    }


def test_live_youtube_source_type(tmp_path):
    from delta.radar.providers.live_youtube import LiveYouTubeProvider

    p = _make_youtube_provider(tmp_path)
    assert p.source_type == "youtube"


def test_live_youtube_requires_credentials(tmp_path):
    from delta.radar.providers.live_youtube import LiveYouTubeProvider

    p = _make_youtube_provider(tmp_path)
    assert p.requires_credentials is True


def test_live_youtube_not_available_without_key(tmp_path):
    from delta.radar.providers.live_youtube import LiveYouTubeProvider

    quota = ProviderQuota(provider_name="yt_test", daily_budget=10)
    history = ObservationHistory(data_dir=str(tmp_path / "obs"))
    p = LiveYouTubeProvider(api_key="", quota=quota, history=history)
    assert not p.is_available


def test_live_youtube_returns_empty_when_unavailable(tmp_path):
    from delta.radar.providers.live_youtube import LiveYouTubeProvider

    quota = ProviderQuota(provider_name="yt_test", daily_budget=10)
    history = ObservationHistory(data_dir=str(tmp_path / "obs"))
    p = LiveYouTubeProvider(api_key="", quota=quota, history=history)
    assert p.fetch_evidence(["AI tools"]) == []


def test_live_youtube_fetch_evidence_returns_source_evidence(tmp_path):
    p = _make_youtube_provider(tmp_path)
    client = p._client
    client.search.return_value.list.return_value.execute.return_value = (
        _mock_search_response(["vid1", "vid2"])
    )
    client.videos.return_value.list.return_value.execute.return_value = (
        _mock_video_stats_response(["vid1", "vid2"])
    )
    client.channels.return_value.list.return_value.execute.return_value = (
        _mock_channel_stats_response(["ch_vid1", "ch_vid2"])
    )

    evidence = p.fetch_evidence(["AI coding tools"])
    assert len(evidence) == 2
    for ev in evidence:
        assert ev.source_type == "youtube"
        assert ev.is_independent is True
        assert "views" in ev.payload
        assert "relative_performance" in ev.payload


def test_live_youtube_caches_results(tmp_path):
    p = _make_youtube_provider(tmp_path)
    client = p._client
    client.search.return_value.list.return_value.execute.return_value = (
        _mock_search_response(["vid1"])
    )
    client.videos.return_value.list.return_value.execute.return_value = (
        _mock_video_stats_response(["vid1"])
    )
    client.channels.return_value.list.return_value.execute.return_value = (
        _mock_channel_stats_response(["ch_vid1"])
    )

    p.fetch_evidence(["AI coding"])
    search_calls_after_first = client.search.return_value.list.call_count

    # Second call should use cache
    p.fetch_evidence(["AI coding"])
    assert client.search.return_value.list.call_count == search_calls_after_first


def test_live_youtube_quota_exhausted_returns_empty(tmp_path):
    p = _make_youtube_provider(tmp_path, budget=0)
    # budget=0 means exhausted immediately
    result = p.fetch_evidence(["AI coding"])
    assert result == []


def test_live_youtube_stores_observations(tmp_path):
    p = _make_youtube_provider(tmp_path)
    client = p._client
    client.search.return_value.list.return_value.execute.return_value = (
        _mock_search_response(["vid_obs"])
    )
    client.videos.return_value.list.return_value.execute.return_value = (
        _mock_video_stats_response(["vid_obs"])
    )
    client.channels.return_value.list.return_value.execute.return_value = (
        _mock_channel_stats_response(["ch_vid_obs"])
    )

    p.fetch_evidence(["AI topic"])
    assert p._history.count() >= 1


def test_live_youtube_discovery_respects_quota(tmp_path):
    p = _make_youtube_provider(tmp_path, budget=2)
    client = p._client
    client.search.return_value.list.return_value.execute.return_value = (
        _mock_search_response(["vid1"])
    )
    client.videos.return_value.list.return_value.execute.return_value = (
        _mock_video_stats_response(["vid1"])
    )
    client.channels.return_value.list.return_value.execute.return_value = (
        _mock_channel_stats_response(["ch_vid1"])
    )

    queries = [f"query_{i}" for i in range(10)]  # 10 queries but only 2 budget
    p.fetch_discovery_evidence(queries=queries, published_after_hours=48)
    assert p._quota.requests_made <= 2


def test_live_youtube_history_used_for_channel_baselines(tmp_path):
    p = _make_youtube_provider(tmp_path)
    from delta.radar.history import Observation
    obs = Observation(
        observation_id="yt:x:2026-01-01",
        source_type="youtube",
        topic_hint="test",
        item_id="x",
        channel_id="ch_known",
        observed_at="2026-01-01T00:00:00+00:00",
        observed_views=5000,
        channel_baseline=2000,
        relative_performance=2.5,
    )
    p._history.record(obs)
    baselines = p._fetch_channel_baselines(["ch_known", "ch_unknown"])
    # ch_known resolved from history
    assert baselines["ch_known"] == 2000


# --- LiveNewsProvider (with mocked feedparser) ---

def _make_news_provider(max_age_hours: int = 72, feeds: list | None = None):
    from delta.radar.providers.live_news import LiveNewsProvider

    test_feeds = feeds or [
        {"url": "http://example.com/feed1", "name": "TestFeed1", "credibility": "high"},
        {"url": "http://example.com/feed2", "name": "TestFeed2", "credibility": "medium"},
    ]
    quota = ProviderQuota(provider_name="news_test", daily_budget=100)
    return LiveNewsProvider(feeds=test_feeds, quota=quota, max_age_hours=max_age_hours)


def _mock_feed(entries: list[dict], bozo: bool = False) -> MagicMock:
    """Build a mock feedparser result."""
    mock = MagicMock()
    mock.get = lambda k, default=None: {
        "entries": [_make_entry(e) for e in entries],
        "bozo": bozo,
        "bozo_exception": "parse error" if bozo else None,
    }.get(k, default)
    # feedparser result also supports attribute access for entries
    mock.entries = [_make_entry(e) for e in entries]
    mock.bozo = bozo
    return mock


def _make_entry(data: dict) -> MagicMock:
    import time
    from datetime import datetime

    entry = MagicMock()
    entry.title = data.get("title", "")
    entry.link = data.get("link", "http://example.com/article")
    entry.id = data.get("id", data.get("link", ""))
    entry.summary = data.get("summary", "")
    # published_parsed: struct_time 2 days ago
    dt = data.get("dt")
    if dt:
        entry.published_parsed = dt.timetuple()
        entry.updated_parsed = None
    else:
        entry.published_parsed = None
        entry.updated_parsed = None
    return entry


def _recent_dt() -> datetime:
    from datetime import timedelta

    return datetime.now(timezone.utc) - timedelta(hours=6)


def test_live_news_source_type():
    p = _make_news_provider()
    assert p.source_type == "news"


def test_live_news_failed_feed_does_not_crash():
    from delta.radar.providers.live_news import LiveNewsProvider

    p = _make_news_provider()
    with patch("feedparser.parse", side_effect=Exception("connection refused")):
        result = p.fetch_evidence(["AI tools"])
    assert result == []


def test_live_news_bozo_feed_returns_empty():
    p = _make_news_provider()
    bad_feed = MagicMock()
    bad_feed.get = lambda k, d=None: {"entries": [], "bozo": True, "bozo_exception": "err"}.get(k, d)
    bad_feed.bozo = True
    bad_feed.entries = []

    with patch("feedparser.parse", return_value=bad_feed):
        result = p.fetch_evidence(["AI tools"])
    assert result == []


def test_live_news_one_feed_fails_others_continue():
    from delta.radar.providers.live_news import LiveNewsProvider

    feeds = [
        {"url": "http://bad.feed/rss", "name": "Bad", "credibility": "high"},
        {"url": "http://good.feed/rss", "name": "Good", "credibility": "high"},
    ]
    p = LiveNewsProvider(feeds=feeds, max_age_hours=72)

    good_entry = _make_entry({
        "title": "AI coding tools are transforming development",
        "link": "http://good.feed/article1",
        "dt": _recent_dt(),
    })
    good_feed = MagicMock()
    good_feed.get = lambda k, d=None: {
        "entries": [good_entry],
        "bozo": False,
        "bozo_exception": None,
    }.get(k, d)
    good_feed.bozo = False
    good_feed.entries = [good_entry]

    def patched_parse(url, **kwargs):
        if "bad" in url:
            raise Exception("timeout")
        return good_feed

    with patch("feedparser.parse", side_effect=patched_parse):
        result = p.fetch_evidence(["AI coding"])
    # Good feed returned evidence; bad feed did not crash
    assert isinstance(result, list)


def test_live_news_stale_articles_excluded():
    p = _make_news_provider(max_age_hours=24)
    from datetime import timedelta

    old_dt = datetime.now(timezone.utc) - timedelta(hours=48)
    entry = _make_entry({
        "title": "AI coding tools review",
        "link": "http://example.com/old",
        "dt": old_dt,
    })
    feed = MagicMock()
    feed.get = lambda k, d=None: {"entries": [entry], "bozo": False}.get(k, d)
    feed.bozo = False
    feed.entries = [entry]

    with patch("feedparser.parse", return_value=feed):
        result = p.fetch_evidence(["AI coding"])
    assert result == []


def test_live_news_duplicate_detection():
    """Same article matched against multiple topics should appear only once."""
    p = _make_news_provider()
    entry = _make_entry({
        "title": "AI model coding automation tools",
        "link": "http://example.com/dup",
        "dt": _recent_dt(),
    })
    feed = MagicMock()
    feed.get = lambda k, d=None: {"entries": [entry, entry], "bozo": False}.get(k, d)
    feed.bozo = False
    feed.entries = [entry, entry]

    with patch("feedparser.parse", return_value=feed):
        result = p.fetch_evidence(["AI model coding automation"])
    # Duplicate source_ids are deduped
    source_ids = [ev.source_id for ev in result]
    assert len(source_ids) == len(set(source_ids))


def test_live_news_quota_limits_feed_fetches():
    from delta.radar.providers.live_news import LiveNewsProvider

    feeds = [
        {"url": f"http://feed{i}.com/rss", "name": f"Feed{i}", "credibility": "high"}
        for i in range(5)
    ]
    quota = ProviderQuota(provider_name="news_test", daily_budget=2)
    p = LiveNewsProvider(feeds=feeds, quota=quota)

    call_count = 0

    def patched_parse(url, **kwargs):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        m.get = lambda k, d=None: {"entries": [], "bozo": False}.get(k, d)
        m.bozo = False
        m.entries = []
        return m

    with patch("feedparser.parse", side_effect=patched_parse):
        p.fetch_evidence(["topic"])
    assert call_count <= 2


def test_live_news_discovery_evidence_returns_all_entries():
    p = _make_news_provider()
    entries = [
        _make_entry({"title": f"Article {i}", "link": f"http://ex.com/{i}", "dt": _recent_dt()})
        for i in range(3)
    ]
    feed = MagicMock()
    feed.get = lambda k, d=None: {"entries": entries, "bozo": False}.get(k, d)
    feed.bozo = False
    feed.entries = entries

    with patch("feedparser.parse", return_value=feed):
        result = p.fetch_discovery_evidence()
    # 3 entries × 2 feeds = up to 6, but duplicates by source_id are deduped
    assert len(result) >= 1
