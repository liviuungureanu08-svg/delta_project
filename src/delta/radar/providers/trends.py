"""Mock search-trends signal provider — fixture-based, no network calls."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .base import RadarSourceProvider, SourceEvidence


def _utc(hours_ago: float = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours_ago)


_FIXTURES: list[dict[str, Any]] = [
    {
        "topic_hint": "Claude AI coding agent",
        "trend_id": "trends_claude_agent",
        "search_term": "Claude AI coding",
        "trend_direction": "rising",
        "relative_interest_now": 88,    # 0–100
        "relative_interest_7d_ago": 42,
        "hours_ago": 6,
    },
    {
        "topic_hint": "AI video generation 2026",
        "trend_id": "trends_ai_video_gen",
        "search_term": "AI video generation",
        "trend_direction": "rising",
        "relative_interest_now": 75,
        "relative_interest_7d_ago": 55,
        "hours_ago": 6,
    },
    {
        "topic_hint": "AI memory systems",
        "trend_id": "trends_ai_memory",
        "search_term": "AI memory context",
        "trend_direction": "rising",
        "relative_interest_now": 28,
        "relative_interest_7d_ago": 12,
        "hours_ago": 90,  # stale for ai_tech (> 72h window)
    },
    {
        "topic_hint": "keyboard shortcuts productivity",
        "trend_id": "trends_keyboard",
        "search_term": "keyboard shortcuts",
        "trend_direction": "stable",
        "relative_interest_now": 60,
        "relative_interest_7d_ago": 58,
        "hours_ago": 6,
    },
    {
        "topic_hint": "AI image generation",
        "trend_id": "trends_ai_image",
        "search_term": "AI image generator",
        "trend_direction": "stable",
        "relative_interest_now": 90,
        "relative_interest_7d_ago": 87,
        "hours_ago": 6,
    },
    {
        "topic_hint": "global tariff impact small business",
        "trend_id": "trends_tariffs_2026",
        "search_term": "tariff impact 2026",
        "trend_direction": "rising",
        "relative_interest_now": 82,
        "relative_interest_7d_ago": 34,
        "hours_ago": 8,
    },
]


class MockTrendsProvider(RadarSourceProvider):
    """Fixture-based search-trends provider. No network calls or credentials."""

    @property
    def source_type(self) -> str:
        return "trends"

    def fetch_evidence(self, topics: list[str]) -> list[SourceEvidence]:
        results: list[SourceEvidence] = []
        topic_lower = {t.lower() for t in topics}

        for fixture in _FIXTURES:
            hint = fixture["topic_hint"].lower()
            if not any(hint in t or t in hint or _word_overlap(hint, t) for t in topic_lower):
                continue

            obs_at = _utc(fixture["hours_ago"])
            prev = fixture["relative_interest_7d_ago"]
            curr = fixture["relative_interest_now"]
            acceleration = (curr - prev) / max(prev, 1)

            results.append(SourceEvidence(
                topic_hint=fixture["topic_hint"],
                source_type="trends",
                source_id=fixture["trend_id"],
                observed_at=obs_at,
                evidence_type="search_trend",
                payload={
                    "search_term": fixture["search_term"],
                    "trend_direction": fixture["trend_direction"],
                    "relative_interest_now": curr,
                    "relative_interest_7d_ago": prev,
                    "acceleration_ratio": round(acceleration, 3),
                },
                base_confidence=0.75,
                is_independent=True,
            ))
        return results


_STOP_WORDS = {"ai", "the", "a", "an", "in", "of", "for", "and", "or", "to", "2026", "2025"}


def _word_overlap(a: str, b: str) -> bool:
    """True only if 2+ significant (non-stop) words overlap."""
    words_a = {w for w in a.split() if w not in _STOP_WORDS}
    words_b = {w for w in b.split() if w not in _STOP_WORDS}
    return len(words_a & words_b) >= 2
