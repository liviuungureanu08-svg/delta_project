"""Pre-live-validation blockers: YouTube topic hints, independent-source identity,
and API-key-safe verbose logging. Offline only — no network, no quota."""

import logging
from datetime import datetime, timedelta, timezone

from delta.config import radar_config
from delta.models.radar import Evidence, count_independent_sources
from delta.radar.discovery import TopicDiscovery
from delta.radar.pipeline import RadarPipeline
from delta.radar.providers.base import SourceEvidence
from delta.radar.providers.youtube import MockYouTubeProvider
from delta.radar.providers.news import MockNewsProvider
from delta.radar.signals import SignalNormalizer, evidence_from_source
from delta.radar.stage2 import _count_independent
from tests.test_live_providers import _make_youtube_provider


# --- A1: YouTube topic hint derived from video title ---

def _yt_search(videos: list[tuple[str, str, str]]) -> dict:
    """videos: (video_id, channel_id, title)."""
    return {"items": [
        {"id": {"videoId": vid}, "snippet": {
            "title": title, "channelId": ch, "publishedAt": "2026-01-01T00:00:00Z",
        }}
        for vid, ch, title in videos
    ]}


def _yt_evidence(tmp_path, query: str, videos: list[tuple[str, str, str]]):
    p = _make_youtube_provider(tmp_path, budget=50)
    client = p._client
    client.search.return_value.list.return_value.execute.return_value = _yt_search(videos)
    client.videos.return_value.list.return_value.execute.return_value = {"items": [
        {"id": vid, "statistics": {"viewCount": "5000"}, "snippet": {"channelId": ch}}
        for vid, ch, _ in videos
    ]}
    client.channels.return_value.list.return_value.execute.return_value = {"items": [
        {"id": ch, "statistics": {"subscriberCount": "100000"}} for _, ch, _ in videos
    ]}
    return p.fetch_discovery_evidence(queries=[query], published_after_hours=48)


def test_youtube_same_event_titles_cluster(tmp_path):
    ev = _yt_evidence(tmp_path, "AI coding tool", [
        ("v1", "chA", "OpenAI Launches GPT-6 Agent Mode — Everything You Need to Know"),
        ("v2", "chB", "GPT-6 Agent Mode is INSANE (OpenAI)"),
    ])
    assert all(e.topic_hint != "AI coding tool" for e in ev)
    clusters = TopicDiscovery().discover(ev)
    assert len(clusters) == 1
    assert len(clusters[0].items) == 2


def test_youtube_title_hint_merges_with_rss_hint(tmp_path):
    from delta.radar.providers.live_news import _normalize_news_topic_hint

    ev = _yt_evidence(tmp_path, "AI coding tool", [
        ("v1", "chA", "GPT-6 Agent Mode is INSANE (OpenAI)"),
    ])
    rss = SourceEvidence(
        topic_hint=_normalize_news_topic_hint("OpenAI unveils GPT-6 agent mode for developers"),
        source_type="news", source_id="a1", observed_at=datetime.now(timezone.utc),
        evidence_type="news_mention", payload={"source_name": "The Verge"},
    )
    clusters = TopicDiscovery().discover(ev + [rss])
    assert len(clusters) == 1
    assert clusters[0].source_types == {"youtube", "news"}


def test_youtube_unrelated_titles_stay_separate(tmp_path):
    ev = _yt_evidence(tmp_path, "AI coding tool", [
        ("v1", "chA", "OpenAI Launches GPT-6 Agent Mode"),
        ("v2", "chB", "Tesla Recalls Cybertruck Over Brake Defect"),
    ])
    assert len(TopicDiscovery().discover(ev)) == 2


def test_youtube_payload_preserves_query(tmp_path):
    ev = _yt_evidence(tmp_path, "AI coding tool", [
        ("v1", "chA", "OpenAI Launches GPT-6 Agent Mode"),
    ])
    [e] = ev
    assert e.payload["query"] == "AI coding tool"
    assert e.payload["title"] == "OpenAI Launches GPT-6 Agent Mode"
    assert e.payload["channel_id"] == "chA"
    assert e.payload["video_id"] == "v1"


def test_youtube_empty_title_falls_back_to_query(tmp_path):
    [e] = _yt_evidence(tmp_path, "AI coding tool", [("v1", "chA", "")])
    assert e.topic_hint == "AI coding tool"


# --- A2: independent source = channel / outlet ---

_NOW = datetime.now(timezone.utc) - timedelta(hours=2)


def _yt(vid: str, channel: str) -> Evidence:
    return Evidence("youtube", vid, _NOW, "youtube_video",
                    {"video_id": vid, "channel_id": channel}, 0.8, True)


def _news(art: str, outlet: str) -> Evidence:
    return Evidence("news", art, _NOW, "news_mention",
                    {"source_name": outlet}, 0.9, True)


def _all_counts(evidence: list[Evidence]) -> set[int]:
    """Count via every stage; they must agree."""
    signals = SignalNormalizer(radar_config()["radar"]).normalize(evidence, "ai_tech")
    cluster = TopicDiscovery().discover([
        SourceEvidence("topic", e.source_type, e.source_id, e.observed_at,
                       e.evidence_type, e.observed_value, e.confidence, e.is_independent)
        for e in evidence
    ])
    assert len(cluster) == 1
    return {
        count_independent_sources(evidence),
        signals.independent_source_count,
        _count_independent(evidence),
        cluster[0].independent_source_count,
    }


def test_three_videos_one_channel_is_one_source():
    assert _all_counts([_yt("v1", "chA"), _yt("v2", "chA"), _yt("v3", "chA")]) == {1}


def test_videos_two_channels_is_two_sources():
    assert _all_counts([_yt("v1", "chA"), _yt("v2", "chA"), _yt("v3", "chB")]) == {2}


def test_articles_one_outlet_is_one_source():
    assert _all_counts([_news("a1", "TechCrunch"), _news("a2", "TechCrunch"),
                        _news("a3", " techcrunch ")]) == {1}


def test_articles_two_outlets_is_two_sources():
    assert _all_counts([_news("a1", "TechCrunch"), _news("a2", "Wired")]) == {2}


def test_mixed_youtube_and_rss():
    ev = [_yt("v1", "chA"), _yt("v2", "chA"), _yt("v3", "chB"),
          _news("a1", "Wired"), _news("a2", "Wired")]
    assert _all_counts(ev) == {3}


def test_legacy_evidence_without_identity_falls_back_to_source_id():
    ev = [Evidence("trends", "t1", _NOW, "search_trend", {}, 0.7, True),
          Evidence("trends", "t2", _NOW, "search_trend", {}, 0.7, True),
          Evidence("youtube", "v9", _NOW, "youtube_video", 42, 0.7, True)]
    assert _all_counts(ev) == {3}


def test_mock_fixtures_use_channel_and_outlet_identity():
    """Mock fixtures carry channel_id / source_name, so they exercise the new
    identity rules rather than the source_id fallback."""
    yt = [evidence_from_source(e) for e in MockYouTubeProvider().fetch_evidence(
        ["Claude AI coding agent"])]
    news = [evidence_from_source(e) for e in MockNewsProvider().fetch_evidence(
        ["Claude AI coding agent"])]
    assert yt and news
    assert all(e.observed_value.get("channel_id") for e in yt)
    assert all(e.observed_value.get("source_name") for e in news)
    channels = {e.observed_value["channel_id"] for e in yt}
    outlets = {e.observed_value["source_name"] for e in news}
    assert count_independent_sources(yt + news) == len(channels) + len(outlets)
    # Rewriting every fixture to a single channel collapses them to one source.
    same = [_yt(e.source_id, "one_channel") for e in yt]
    assert count_independent_sources(same) == 1


def _se_news(art: str, outlet: str) -> SourceEvidence:
    return SourceEvidence("claude coding agent", "news", art, _NOW, "news_mention",
                          {"source_name": outlet}, 0.9, True)


def test_pipeline_same_outlet_articles_do_not_validate():
    pipeline = RadarPipeline(radar_config()["radar"])
    top5 = pipeline.run([{
        "topic": "claude coding agent", "niche": "ai_tech",
        "discovery_evidence": [_se_news("a1", "X"), _se_news("a2", "X")],
    }], providers=[])
    [c] = pipeline.last_candidate_diagnostics
    assert top5.reports == []
    assert c["independent_source_count"] == 1
    assert c["distinct_news_outlets"] == 1
    assert c["lifecycle_after_stage2"] == "WATCH"


def test_pipeline_diagnostics_report_distinct_channels_and_outlets():
    yt = [SourceEvidence("claude coding agent", "youtube", v, _NOW, "youtube_video",
                         {"channel_id": ch, "relative_performance": 1.0}, 0.8, True)
          for v, ch in [("v1", "chA"), ("v2", "chA"), ("v3", "chB")]]
    pipeline = RadarPipeline(radar_config()["radar"])
    pipeline.run([{
        "topic": "claude coding agent", "niche": "ai_tech",
        "discovery_evidence": yt + [_se_news("a1", "X"), _se_news("a2", "X")],
    }], providers=[])
    [c] = pipeline.last_candidate_diagnostics
    assert c["distinct_youtube_channels"] == 2
    assert c["distinct_news_outlets"] == 1
    assert c["fallback_source_id_sources"] == 0
    assert c["independent_source_count"] == 3


# --- A3: googleapiclient must not log the API key under --verbose ---

def test_verbose_logging_suppresses_google_client_request_urls(caplog):
    from delta.radar.daily import _configure_logging

    secret = "FAKEKEY_abc123"
    caplog.set_level(logging.DEBUG)
    try:
        _configure_logging(verbose=True)
        logging.getLogger("googleapiclient.discovery").debug(
            "URL being requested: GET https://youtube.googleapis.com/youtube/v3/"
            "search?q=x&key=%s&alt=json", secret)
        logging.getLogger("googleapiclient.discovery").info(
            "URL being requested: key=%s", secret)
        logging.getLogger("delta.radar.test").debug("delta debug still visible")
    finally:
        logging.getLogger("googleapiclient").setLevel(logging.NOTSET)
    assert secret not in caplog.text
    assert "delta debug still visible" in caplog.text
