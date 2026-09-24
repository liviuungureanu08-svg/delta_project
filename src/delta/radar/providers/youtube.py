"""Mock YouTube signal provider — fixture-based, no network calls, no credentials."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .base import RadarSourceProvider, SourceEvidence


def _utc(hours_ago: float = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours_ago)


# Fixture data: realistic mock YouTube signal observations
_FIXTURES: list[dict[str, Any]] = [
    {
        "topic_hint": "Claude AI coding agent",
        "video_id": "yt_mock_001",
        "channel_id": "ch_aitech_a",
        "title": "I Let Claude Code My Entire App — Here's What Happened",
        "published_hours_ago": 36,
        "views": 142_000,
        "channel_baseline_views": 18_000,
        "channel_upload_frequency_days": 7,
        "tags": ["claude ai", "ai coding", "claude agent"],
    },
    {
        "topic_hint": "Claude AI coding agent",
        "video_id": "yt_mock_002",
        "channel_id": "ch_aitech_b",
        "title": "Claude vs Cursor — Which AI Codes Better?",
        "published_hours_ago": 48,
        "views": 89_000,
        "channel_baseline_views": 12_000,
        "channel_upload_frequency_days": 5,
        "tags": ["claude ai", "cursor", "ai coding"],
    },
    {
        "topic_hint": "Claude AI coding agent",
        "video_id": "yt_mock_003",
        "channel_id": "ch_aitech_c",
        "title": "Claude Code Is Changing Everything",
        "published_hours_ago": 24,
        "views": 34_000,
        "channel_baseline_views": 9_000,
        "channel_upload_frequency_days": 14,
        "tags": ["claude code", "ai tools"],
    },
    {
        "topic_hint": "AI video generation 2026",
        "video_id": "yt_mock_010",
        "channel_id": "ch_aitools_x",
        "title": "New AI Video Generator Blew My Mind",
        "published_hours_ago": 72,
        "views": 67_000,
        "channel_baseline_views": 22_000,
        "channel_upload_frequency_days": 10,
        "tags": ["ai video", "video generation", "ai tools"],
    },
    {
        "topic_hint": "AI video generation 2026",
        "video_id": "yt_mock_011",
        "channel_id": "ch_aitools_y",
        "title": "I Made a Full Movie With AI in 2 Hours",
        "published_hours_ago": 96,
        "views": 210_000,
        "channel_baseline_views": 25_000,
        "channel_upload_frequency_days": 7,
        "tags": ["ai video", "video generation"],
    },
    {
        "topic_hint": "AI video generation 2026",
        "video_id": "yt_mock_012",
        "channel_id": "ch_tech_z",
        "title": "Every AI Video Tool Compared 2026",
        "published_hours_ago": 120,
        "views": 310_000,
        "channel_baseline_views": 30_000,
        "channel_upload_frequency_days": 7,
        "tags": ["ai video", "comparison"],
    },
    # WATCH candidate — small signal, promising but early
    {
        "topic_hint": "AI memory systems",
        "video_id": "yt_mock_020",
        "channel_id": "ch_indie_m",
        "title": "What If AI Could Remember Everything?",
        "published_hours_ago": 18,
        "views": 8_200,
        "channel_baseline_views": 1_500,
        "channel_upload_frequency_days": 21,
        "tags": ["ai memory", "long context", "ai agents"],
    },
    # FALSE POSITIVE — single large channel spike, not breakout
    {
        "topic_hint": "keyboard shortcuts productivity",
        "video_id": "yt_mock_030",
        "channel_id": "ch_mega_1",
        "title": "100 Keyboard Shortcuts You Need to Know",
        "published_hours_ago": 48,
        "views": 500_000,
        "channel_baseline_views": 450_000,
        "channel_upload_frequency_days": 3,
        "tags": ["productivity", "keyboard shortcuts"],
    },
    # SATURATED — AI image generation (topic has many existing videos)
    {
        "topic_hint": "AI image generation",
        "video_id": "yt_mock_040",
        "channel_id": "ch_imggen_a",
        "title": "Best AI Image Generator 2026",
        "published_hours_ago": 24,
        "views": 95_000,
        "channel_baseline_views": 40_000,
        "channel_upload_frequency_days": 4,
        "tags": ["ai image", "midjourney", "stable diffusion"],
    },
    # CROSS-NICHE breakout — finance/economics topic
    {
        "topic_hint": "global tariff impact small business",
        "video_id": "yt_mock_050",
        "channel_id": "ch_finance_a",
        "title": "How New Tariffs Will Destroy Small Businesses in 2026",
        "published_hours_ago": 30,
        "views": 380_000,
        "channel_baseline_views": 45_000,
        "channel_upload_frequency_days": 5,
        "tags": ["tariffs", "small business", "economy", "2026"],
    },
    {
        "topic_hint": "global tariff impact small business",
        "video_id": "yt_mock_051",
        "channel_id": "ch_finance_b",
        "title": "The Tariff Crisis Is Just Getting Started",
        "published_hours_ago": 48,
        "views": 195_000,
        "channel_baseline_views": 28_000,
        "channel_upload_frequency_days": 7,
        "tags": ["tariffs", "economy", "trade war"],
    },
]


class MockYouTubeProvider(RadarSourceProvider):
    """Fixture-based YouTube signal provider. No network calls or credentials."""

    @property
    def source_type(self) -> str:
        return "youtube"

    def fetch_evidence(self, topics: list[str]) -> list[SourceEvidence]:
        results: list[SourceEvidence] = []
        topic_lower = {t.lower() for t in topics}

        for fixture in _FIXTURES:
            hint = fixture["topic_hint"].lower()
            if not any(hint in t or t in hint or _word_overlap(hint, t) for t in topic_lower):
                continue

            obs_at = _utc(fixture["published_hours_ago"])
            results.append(SourceEvidence(
                topic_hint=fixture["topic_hint"],
                source_type="youtube",
                source_id=fixture["video_id"],
                observed_at=obs_at,
                evidence_type="youtube_video",
                payload={
                    "video_id": fixture["video_id"],
                    "channel_id": fixture["channel_id"],
                    "title": fixture["title"],
                    "views": fixture["views"],
                    "channel_baseline_views": fixture["channel_baseline_views"],
                    "channel_upload_frequency_days": fixture["channel_upload_frequency_days"],
                    "observation_age_hours": fixture["published_hours_ago"],
                    "relative_performance": (
                        fixture["views"] / fixture["channel_baseline_views"]
                        if fixture["channel_baseline_views"] > 0 else 0.0
                    ),
                    "tags": fixture["tags"],
                },
                base_confidence=0.80,
                is_independent=True,
            ))
        return results


_STOP_WORDS = {"ai", "the", "a", "an", "in", "of", "for", "and", "or", "to", "2026", "2025"}


def _word_overlap(a: str, b: str) -> bool:
    """True only if 2+ significant (non-stop) words overlap."""
    words_a = {w for w in a.split() if w not in _STOP_WORDS}
    words_b = {w for w in b.split() if w not in _STOP_WORDS}
    return len(words_a & words_b) >= 2
