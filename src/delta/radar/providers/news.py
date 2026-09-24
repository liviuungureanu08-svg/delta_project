"""Mock news/current-events signal provider — fixture-based, no network calls."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .base import RadarSourceProvider, SourceEvidence


def _utc(hours_ago: float = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours_ago)


_FIXTURES: list[dict[str, Any]] = [
    {
        "topic_hint": "Claude AI coding agent",
        "article_id": "news_claude_001",
        "source_name": "TechCrunch",
        "headline": "Anthropic's Claude Becomes the Coding Agent of Choice for Developers",
        "hours_ago": 20,
        "source_credibility": "high",
    },
    {
        "topic_hint": "Claude AI coding agent",
        "article_id": "news_claude_002",
        "source_name": "The Verge",
        "headline": "Claude Code Is Quietly Taking Over Software Development",
        "hours_ago": 30,
        "source_credibility": "high",
    },
    {
        "topic_hint": "AI video generation 2026",
        "article_id": "news_aivid_001",
        "source_name": "Wired",
        "headline": "AI Video Generation Has Crossed the Uncanny Valley",
        "hours_ago": 48,
        "source_credibility": "high",
    },
    {
        "topic_hint": "AI memory systems",
        "article_id": "news_aimem_001",
        "source_name": "MIT Technology Review",
        "headline": "The Next Frontier for AI: Persistent Memory",
        "hours_ago": 80,  # stale for ai_tech (> 72h window) — early days signal
        "source_credibility": "high",
    },
    # Single low-credibility source — false positive risk
    {
        "topic_hint": "keyboard shortcuts productivity",
        "article_id": "news_kb_001",
        "source_name": "ProductivityBlog.io",
        "headline": "These Keyboard Shortcuts Will Change Your Life",
        "hours_ago": 12,
        "source_credibility": "low",
    },
    {
        "topic_hint": "AI image generation",
        "article_id": "news_aiimg_001",
        "source_name": "Forbes",
        "headline": "AI Image Generation Market Worth $X Billion by 2028",
        "hours_ago": 96,
        "source_credibility": "medium",
    },
    {
        "topic_hint": "global tariff impact small business",
        "article_id": "news_tariff_001",
        "source_name": "Reuters",
        "headline": "New Tariff Regime Threatens Millions of Small Businesses Globally",
        "hours_ago": 24,
        "source_credibility": "high",
    },
    {
        "topic_hint": "global tariff impact small business",
        "article_id": "news_tariff_002",
        "source_name": "Bloomberg",
        "headline": "Trade War Escalation: Small Business Owners Brace for Impact",
        "hours_ago": 36,
        "source_credibility": "high",
    },
    {
        "topic_hint": "global tariff impact small business",
        "article_id": "news_tariff_003",
        "source_name": "AP News",
        "headline": "Economists Warn Tariff Shock Will Hit Main Street Hardest",
        "hours_ago": 18,
        "source_credibility": "high",
    },
]

_CREDIBILITY_SCORE = {"high": 0.90, "medium": 0.65, "low": 0.30}


class MockNewsProvider(RadarSourceProvider):
    """Fixture-based news signal provider. No network calls or credentials."""

    @property
    def source_type(self) -> str:
        return "news"

    def fetch_evidence(self, topics: list[str]) -> list[SourceEvidence]:
        results: list[SourceEvidence] = []
        topic_lower = {t.lower() for t in topics}

        for fixture in _FIXTURES:
            hint = fixture["topic_hint"].lower()
            if not any(hint in t or t in hint or _word_overlap(hint, t) for t in topic_lower):
                continue

            obs_at = _utc(fixture["hours_ago"])
            cred = fixture["source_credibility"]
            conf = _CREDIBILITY_SCORE.get(cred, 0.5)

            results.append(SourceEvidence(
                topic_hint=fixture["topic_hint"],
                source_type="news",
                source_id=fixture["article_id"],
                observed_at=obs_at,
                evidence_type="news_mention",
                payload={
                    "source_name": fixture["source_name"],
                    "headline": fixture["headline"],
                    "source_credibility": cred,
                },
                base_confidence=conf,
                is_independent=True,
            ))
        return results


_STOP_WORDS = {"ai", "the", "a", "an", "in", "of", "for", "and", "or", "to", "2026", "2025"}


def _word_overlap(a: str, b: str) -> bool:
    """True only if 2+ significant (non-stop) words overlap."""
    words_a = {w for w in a.split() if w not in _STOP_WORDS}
    words_b = {w for w in b.split() if w not in _STOP_WORDS}
    return len(words_a & words_b) >= 2
