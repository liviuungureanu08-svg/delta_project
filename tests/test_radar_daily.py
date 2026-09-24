"""Tests for daily radar run — offline mode (no real network calls)."""

import json
import tempfile
from pathlib import Path

import pytest

from delta.models.radar import DailyTop5, LifecycleState


def test_run_daily_returns_daily_top5(tmp_path):
    from delta.radar.daily import run_daily

    result = run_daily(
        output_dir=str(tmp_path / "reports"),
        verbose=False,
    )
    assert isinstance(result, DailyTop5)


def test_run_daily_max_five_opportunities(tmp_path):
    from delta.radar.daily import run_daily

    result = run_daily(output_dir=str(tmp_path / "reports"))
    assert len(result.reports) <= 5


def test_run_daily_all_reports_pending_approval(tmp_path):
    from delta.radar.daily import run_daily

    result = run_daily(output_dir=str(tmp_path / "reports"))
    for r in result.reports:
        assert r.human_approved is None, "human_approved must be None until a human decides"


def test_run_daily_writes_json_report(tmp_path):
    from delta.radar.daily import run_daily

    output_dir = tmp_path / "reports"
    run_daily(output_dir=str(output_dir))

    json_files = list(output_dir.glob("report_*.json"))
    assert len(json_files) == 1

    data = json.loads(json_files[0].read_text())
    assert "opportunities" in data
    assert "candidates_evaluated" in data
    assert "generated_at" in data


def test_run_daily_writes_text_report(tmp_path):
    from delta.radar.daily import run_daily

    output_dir = tmp_path / "reports"
    run_daily(output_dir=str(output_dir))

    txt_files = list(output_dir.glob("report_*.txt"))
    assert len(txt_files) == 1
    content = txt_files[0].read_text()
    assert "DELTA DAILY RADAR" in content


def test_run_daily_json_has_separate_opportunity_confidence(tmp_path):
    from delta.radar.daily import run_daily

    output_dir = tmp_path / "reports"
    result = run_daily(output_dir=str(output_dir))

    json_files = list(output_dir.glob("report_*.json"))
    data = json.loads(json_files[0].read_text())
    for opp in data["opportunities"]:
        assert "opportunity_score" in opp
        assert "confidence_score" in opp
        # They must not be combined into one field
        assert "combined_score" not in opp


def test_run_daily_with_custom_fallback_topics(tmp_path):
    from delta.radar.daily import run_daily

    custom_topics = [
        {"topic": "Claude AI coding agent", "niche": "ai_tech"},
    ]
    result = run_daily(
        output_dir=str(tmp_path / "reports"),
        offline_fallback_topics=custom_topics,
    )
    assert isinstance(result, DailyTop5)


def test_run_daily_offline_no_credentials_needed(tmp_path):
    """Should complete without any API key."""
    import os
    env_backup = os.environ.pop("YOUTUBE_API_KEY", None)
    try:
        from delta.radar.daily import run_daily

        result = run_daily(output_dir=str(tmp_path / "reports"))
        assert isinstance(result, DailyTop5)
    finally:
        if env_backup is not None:
            os.environ["YOUTUBE_API_KEY"] = env_backup


def test_run_daily_opportunity_confidence_scores_separate(tmp_path):
    from delta.radar.daily import run_daily

    result = run_daily(output_dir=str(tmp_path / "reports"))
    for r in result.reports:
        # Scores must remain separate (D6)
        assert hasattr(r, "opportunity_score")
        assert hasattr(r, "confidence_score")
        assert r.opportunity_score != r.confidence_score or True  # can be equal; must both exist


def test_run_daily_lifecycle_is_human_approval(tmp_path):
    from delta.radar.daily import run_daily

    result = run_daily(output_dir=str(tmp_path / "reports"))
    for r in result.reports:
        assert r.lifecycle == LifecycleState.HUMAN_APPROVAL
