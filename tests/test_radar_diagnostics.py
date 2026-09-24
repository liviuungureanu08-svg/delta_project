"""Tests for live radar diagnostics — mocks only; no real network calls."""

import json
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from delta.config import radar_config
from delta.radar.pipeline import RadarPipeline
from delta.radar.providers.base import SourceEvidence
from tests.test_live_providers import (
    _make_news_provider,
    _make_youtube_provider,
    _mock_channel_stats_response,
    _mock_feed,
    _mock_search_response,
    _mock_video_stats_response,
)

_SECRET = "SUPERSECRETKEY123"


# --- YouTube ---

def test_youtube_diagnostics_records_items_per_query(tmp_path):
    p = _make_youtube_provider(tmp_path, budget=1)
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

    p.fetch_discovery_evidence(["AI coding tool", "AI agent framework"])
    diag = p.diagnostics()

    assert diag["provider_initialized"] is True
    assert diag["search_failures"] == 0
    assert diag["quota"]["requests_made"] == 1
    assert diag["total_discovery_evidence"] == 2
    q1, q2 = diag["discovery_queries"]
    assert q1 == {
        "query": "AI coding tool", "status": "ok", "search_items": 2,
        "evidence_items": 2, "error": None,
    }
    assert q2["query"] == "AI agent framework"
    assert q2["status"] == "not_run_quota"


def test_youtube_search_failure_is_recorded_without_key(tmp_path, caplog):
    p = _make_youtube_provider(tmp_path, api_key=_SECRET)
    p._client.search.return_value.list.return_value.execute.side_effect = Exception(
        f"<HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/"
        f"search?q=ai&key={_SECRET}&alt=json returned 'quotaExceeded'>"
    )

    with caplog.at_level(logging.WARNING):
        evidence = p.fetch_discovery_evidence(["AI coding tool"])
    diag = p.diagnostics()

    assert evidence == []
    assert diag["search_failures"] == 1
    entry = diag["discovery_queries"][0]
    assert entry["status"] == "search_failed"
    assert entry["search_items"] == 0
    assert _SECRET not in json.dumps(diag)
    assert _SECRET not in caplog.text


# --- RSS ---

def test_rss_diagnostics_entries_and_fresh_per_feed():
    p = _make_news_provider(max_age_hours=72)
    fresh = datetime.now(timezone.utc) - timedelta(hours=6)
    stale = datetime.now(timezone.utc) - timedelta(hours=200)
    feed1 = _mock_feed([
        {"title": "Fresh one", "link": "http://a/1", "dt": fresh},
        {"title": "Stale one", "link": "http://a/2", "dt": stale},
    ])

    def fake_parse(url, **kwargs):
        if url.endswith("feed1"):
            return feed1
        raise Exception("connection refused")

    with patch("feedparser.parse", side_effect=fake_parse):
        evidence = p.fetch_discovery_evidence()
    diag = p.diagnostics()

    assert len(evidence) == diag["total_fresh_discovery_evidence"]
    f1, f2 = diag["feeds"]["TestFeed1"], diag["feeds"]["TestFeed2"]
    assert f1["status"] == "ok" and f1["entries"] == 2
    assert f1["fresh_items"] == len(evidence)
    assert f2["status"] == "fetch_failed" and f2["entries"] == 0
    assert "connection refused" in f2["error"]


# --- Per-candidate ---

def _news_ev(source_id: str, hint: str) -> SourceEvidence:
    return SourceEvidence(
        topic_hint=hint, source_type="news", source_id=source_id,
        observed_at=datetime.now(timezone.utc) - timedelta(hours=3),
        evidence_type="news_mention", payload={"source_name": "X"},
        base_confidence=0.9, is_independent=True,
    )


def test_pipeline_candidate_diagnostics_single_source_rejected():
    pipeline = RadarPipeline(radar_config()["radar"])
    inputs = [{
        "topic": "claude coding agent", "niche": "ai_tech",
        "discovery_evidence": [_news_ev("news_1", "claude coding agent")],
    }]

    top5 = pipeline.run(inputs, providers=[])
    [c] = pipeline.last_candidate_diagnostics

    assert top5.reports == []
    assert c["topic"] == "claude coding agent"
    assert c["evidence_source_types"] == {"news": 1}
    assert c["evidence_item_count"] == 1
    assert c["independent_source_count"] == 1
    assert c["lifecycle_after_stage1"] == "WATCH"
    assert c["lifecycle_after_stage2"] == "WATCH"
    assert c["selected_for_top5"] is False
    assert "Only 1 independent source(s); need 2." in c["main_risk"]
    assert c["rejection_reason"].startswith("Lifecycle WATCH < VALIDATED (Stage 2:")


def test_pipeline_candidate_diagnostics_selected_has_no_rejection():
    pipeline = RadarPipeline(radar_config()["radar"])
    inputs = [{
        "topic": "claude coding agent", "niche": "ai_tech",
        "discovery_evidence": [
            _news_ev("news_1", "claude coding agent"),
            _news_ev("news_2", "claude coding agent"),
        ],
    }]

    top5 = pipeline.run(inputs, providers=[])
    [c] = pipeline.last_candidate_diagnostics

    assert len(top5.reports) == 1
    assert c["lifecycle_after_stage2"] == "VALIDATED"
    assert c["selected_for_top5"] is True
    assert c["rejection_reason"] is None


# --- Daily report ---

def test_daily_report_has_diagnostics_and_preserves_fields(tmp_path, monkeypatch):
    from delta.radar.daily import run_daily

    monkeypatch.setenv("YOUTUBE_API_KEY", _SECRET)
    out = tmp_path / "reports"
    top5 = run_daily(output_dir=str(out))

    [path] = list(out.glob("report_*.json"))
    raw = path.read_text()
    data = json.loads(raw)

    for key in ("generated_at", "run_date", "candidates_evaluated",
                "candidates_rejected", "opportunities"):
        assert key in data
    diag = data["diagnostics"]
    assert set(diag) >= {"live_enabled", "discovery_mode", "youtube", "rss", "candidates"}
    assert len(diag["candidates"]) == top5.candidates_evaluated
    assert "total_fresh_evidence" in diag["youtube"]
    assert "total_fresh_evidence" in diag["rss"]
    assert _SECRET not in raw
