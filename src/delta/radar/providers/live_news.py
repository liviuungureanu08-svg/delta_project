"""Live multi-source RSS/feed news provider.

Goals:
  - Detect fresh events and confirm cross-source topic appearances.
  - Configurable reputable sources; not dependent on any single publisher.
  - Graceful per-feed failure: one broken feed never crashes the radar.
  - No article body scraping — headlines and feed descriptions only.
"""

from __future__ import annotations

import hashlib
import logging
import socket
from datetime import datetime, timezone
from typing import Optional

from delta.radar.providers.base import RadarSourceProvider, SourceEvidence
from delta.radar.quota import ProviderQuota

logger = logging.getLogger(__name__)


_DEFAULT_FEEDS: list[dict] = [
    {
        "url": "https://feeds.feedburner.com/TechCrunch",
        "name": "TechCrunch",
        "credibility": "high",
    },
    {
        "url": "https://www.wired.com/feed/rss",
        "name": "Wired",
        "credibility": "high",
    },
    {
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "name": "Ars Technica",
        "credibility": "high",
    },
    {
        "url": "https://www.theverge.com/rss/index.xml",
        "name": "The Verge",
        "credibility": "high",
    },
    {
        "url": "https://feeds.reuters.com/reuters/technologyNews",
        "name": "Reuters Tech",
        "credibility": "high",
    },
    {
        "url": "https://venturebeat.com/feed/",
        "name": "VentureBeat",
        "credibility": "medium",
    },
    {
        "url": "https://www.zdnet.com/news/rss.xml",
        "name": "ZDNet",
        "credibility": "medium",
    },
    {
        "url": "https://www.technologyreview.com/feed/",
        "name": "MIT Technology Review",
        "credibility": "high",
    },
]

_CREDIBILITY_SCORE: dict[str, float] = {
    "high": 0.90,
    "medium": 0.65,
    "low": 0.30,
}


def _article_id(url: str) -> str:
    return "news_" + hashlib.md5(url.encode()).hexdigest()[:12]


def _parse_entry_time(entry: object) -> Optional[datetime]:
    """Extract published datetime from feedparser entry (best-effort)."""
    import time as _time

    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                ts = _time.mktime(val)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                pass
    return None


def _entry_matches(entry_text: str, topic: str) -> bool:
    """Return True if entry text contains enough topic keywords."""
    entry_lower = entry_text.lower()
    topic_words = [w for w in topic.lower().split() if len(w) > 3]
    if len(topic_words) <= 1:
        return topic.lower() in entry_lower
    matches = sum(1 for w in topic_words if w in entry_lower)
    return matches >= max(2, len(topic_words) // 2)


class LiveNewsProvider(RadarSourceProvider):
    """Multi-source RSS/feed provider.

    Feed failures are isolated — a single timeout or parse error
    does not affect other feeds or the overall radar run.
    """

    def __init__(
        self,
        feeds: Optional[list[dict]] = None,
        quota: Optional[ProviderQuota] = None,
        max_age_hours: int = 72,
        timeout_seconds: int = 10,
    ) -> None:
        self._feeds = feeds if feeds is not None else list(_DEFAULT_FEEDS)
        self._quota = quota or ProviderQuota(
            provider_name="news_live",
            daily_budget=len(self._feeds) * 20,
        )
        self._max_age_hours = max_age_hours
        self._timeout = timeout_seconds
        self._feed_cache: dict[str, list[dict]] = {}

    @property
    def source_type(self) -> str:
        return "news"

    def fetch_evidence(self, topics: list[str]) -> list[SourceEvidence]:
        """Fetch news evidence for given topics from all configured feeds."""
        all_entries = self._load_all_feeds()
        results: list[SourceEvidence] = []
        seen_ids: set[str] = set()
        now = datetime.now(timezone.utc)

        for entry in all_entries:
            entry_text = f"{entry.get('title', '')} {entry.get('summary', '')}"

            for topic in topics:
                if not _entry_matches(entry_text, topic):
                    continue

                art_id = entry.get("article_id", "")
                if art_id in seen_ids:
                    break
                seen_ids.add(art_id)

                pub_dt = entry.get("published_at")
                if pub_dt is None:
                    break

                age_hours = (now - pub_dt).total_seconds() / 3600
                if age_hours > self._max_age_hours:
                    break

                cred = entry.get("credibility", "medium")
                conf = _CREDIBILITY_SCORE.get(cred, 0.5)

                results.append(SourceEvidence(
                    topic_hint=topic,
                    source_type="news",
                    source_id=art_id,
                    observed_at=pub_dt,
                    evidence_type="news_mention",
                    payload={
                        "source_name": entry.get("source_name", ""),
                        "headline": entry.get("title", ""),
                        "url": entry.get("link", ""),
                        "source_credibility": cred,
                        "age_hours": round(age_hours, 1),
                    },
                    base_confidence=conf,
                    is_independent=True,
                ))
                break  # one topic match per entry is enough

        return results

    def fetch_discovery_evidence(self) -> list[SourceEvidence]:
        """Return all fresh entries as evidence for autonomous topic discovery."""
        all_entries = self._load_all_feeds()
        results: list[SourceEvidence] = []
        seen_ids: set[str] = set()
        now = datetime.now(timezone.utc)

        for entry in all_entries:
            art_id = entry.get("article_id", "")
            if art_id in seen_ids:
                continue
            seen_ids.add(art_id)

            pub_dt = entry.get("published_at")
            if pub_dt is None:
                continue

            age_hours = (now - pub_dt).total_seconds() / 3600
            if age_hours > self._max_age_hours:
                continue

            cred = entry.get("credibility", "medium")
            conf = _CREDIBILITY_SCORE.get(cred, 0.5)
            topic = entry.get("title", "unknown topic")

            results.append(SourceEvidence(
                topic_hint=topic,
                source_type="news",
                source_id=art_id,
                observed_at=pub_dt,
                evidence_type="news_mention",
                payload={
                    "source_name": entry.get("source_name", ""),
                    "headline": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "source_credibility": cred,
                    "age_hours": round(age_hours, 1),
                },
                base_confidence=conf,
                is_independent=True,
            ))

        return results

    def _load_all_feeds(self) -> list[dict]:
        all_entries: list[dict] = []
        for feed_config in self._feeds:
            url = feed_config.get("url", "")
            if not url:
                continue
            if url not in self._feed_cache:
                self._feed_cache[url] = self._fetch_feed(feed_config)
            all_entries.extend(self._feed_cache[url])
        return all_entries

    def _fetch_feed(self, feed_config: dict) -> list[dict]:
        """Fetch and parse one RSS feed. Returns [] on any failure."""
        import feedparser  # type: ignore

        url = feed_config["url"]
        name = feed_config.get("name", url)
        cred = feed_config.get("credibility", "medium")

        if not self._quota.consume(1):
            return []

        old_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(self._timeout)
            feed = feedparser.parse(
                url,
                request_headers={"User-Agent": "DeltaRadar/3.0"},
            )
        except Exception as exc:
            logger.warning("Feed fetch failed for %s: %s", name, exc)
            self._quota.record_failure()
            return []
        finally:
            socket.setdefaulttimeout(old_timeout)

        if feed.get("bozo") and not feed.get("entries"):
            logger.warning(
                "Feed parse error for %s: %s", name, feed.get("bozo_exception")
            )
            self._quota.record_failure()
            return []

        entries = []
        for entry in feed.get("entries", []):
            link = getattr(entry, "link", "") or ""
            raw_id = getattr(entry, "id", "") or link or getattr(entry, "title", "")
            art_id = _article_id(raw_id)
            pub_dt = _parse_entry_time(entry)

            entries.append({
                "article_id": art_id,
                "source_name": name,
                "credibility": cred,
                "title": getattr(entry, "title", ""),
                "summary": (getattr(entry, "summary", "") or "")[:500],
                "link": link,
                "published_at": pub_dt,
            })

        return entries
