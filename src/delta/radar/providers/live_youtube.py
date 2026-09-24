"""Live YouTube Data API v3 provider.

Requires YOUTUBE_API_KEY environment variable.
Falls back gracefully to empty evidence if unavailable.
Credentials are NEVER logged, committed, or printed.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from delta.radar.history import Observation, ObservationHistory
from delta.radar.providers.base import RadarSourceProvider, SourceEvidence
from delta.radar.quota import ProviderQuota

logger = logging.getLogger(__name__)

_KEY_PARAM_RE = re.compile(r"(key=)[^&\s\"'>]+", re.IGNORECASE)


def _redact(value: object) -> str:
    """Stringify and strip any API key query parameter (HttpError text embeds the URL)."""
    return _KEY_PARAM_RE.sub(r"\1REDACTED", str(value))


def _error_summary(exc: Exception) -> str:
    """Short, key-free description of an API error for diagnostics."""
    status = getattr(getattr(exc, "resp", None), "status", None)
    reason = getattr(exc, "reason", None) or ""
    parts = [type(exc).__name__]
    if status is not None:
        parts.append(str(status))
    summary = " ".join(parts)
    if reason:
        summary += f": {reason}"
    return _redact(summary)[:200]


def _obs_id(video_id: str, date_str: str) -> str:
    return f"yt:{video_id}:{date_str}"


class LiveYouTubeProvider(RadarSourceProvider):
    """YouTube Data API v3 provider.

    Discovery strategies:
      - Keyword/topic searches (uses quota)
      - Recently published videos on configured reference channels
      - WATCH candidate topic queries (prioritized in quota allocation)

    Channel-relative performance:
      Evidence is scored relative to channel_baseline_views, not absolute views.
      Baselines are built from historical observations or estimated from
      subscriber count when history is absent.

    Quota:
      Each search costs 100 YouTube Data API quota units.
      daily_search_budget is expressed in search-request COUNT (not raw units)
      to keep configuration human-readable.
    """

    DEFAULT_DAILY_SEARCH_BUDGET = 50  # search requests per day

    def __init__(
        self,
        api_key: Optional[str] = None,
        quota: Optional[ProviderQuota] = None,
        history: Optional[ObservationHistory] = None,
        config: Optional[dict] = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("YOUTUBE_API_KEY", "")
        self._config = config or {}
        self._quota = quota or ProviderQuota(
            provider_name="youtube_live",
            daily_budget=self._config.get(
                "daily_search_budget", self.DEFAULT_DAILY_SEARCH_BUDGET
            ),
        )
        self._history = history or ObservationHistory()
        self._client: Any = None
        self._available = False
        self._evidence_cache: dict[str, list[SourceEvidence]] = {}  # query → results

        if self._api_key:
            self._init_client()

    def _init_client(self) -> None:
        try:
            from googleapiclient.discovery import build  # type: ignore
            self._client = build(
                "youtube", "v3", developerKey=self._api_key,
                cache_discovery=False,
            )
            self._available = True
            self._quota.available = True
        except Exception as exc:
            logger.warning("YouTube API client init failed: %s", _redact(exc))
            self._diag()["init_error"] = _error_summary(exc)
            self._available = False
            self._quota.available = False

    def _diag(self) -> dict:
        # Lazily created so instances built via __new__ (tests) also work.
        diag = getattr(self, "_diagnostics", None)
        if diag is None:
            diag = {"init_error": None, "discovery_queries": [], "stats_failures": 0}
            self._diagnostics = diag
        return diag

    def diagnostics(self) -> dict:
        """Key-free runtime diagnostics for the daily report."""
        diag = self._diag()
        queries = diag["discovery_queries"]
        return {
            "provider": "live",
            "provider_initialized": bool(self._available and self._client is not None),
            "init_error": diag["init_error"],
            "search_failures": self._quota.failed_requests,
            "stats_failures": diag["stats_failures"],
            "quota": self._quota.to_dict(),
            "discovery_queries": list(queries),
            "total_discovery_evidence": sum(q["evidence_items"] for q in queries),
        }

    @property
    def source_type(self) -> str:
        return "youtube"

    @property
    def requires_credentials(self) -> bool:
        return True

    @property
    def is_available(self) -> bool:
        return self._available and not self._quota.is_exhausted

    def fetch_evidence(self, topics: list[str]) -> list[SourceEvidence]:
        """Fetch evidence for given topics. Uses cache to avoid re-fetching."""
        if not self.is_available:
            return []

        results: list[SourceEvidence] = []
        for topic in topics:
            cache_key = topic.lower()
            if cache_key in self._evidence_cache:
                self._quota.record_cache_hit()
                results.extend(self._evidence_cache[cache_key])
                continue

            try:
                items = self._search_videos(topic, max_results=10)
                evidence = self._process_search_results(topic, items)
                self._evidence_cache[cache_key] = evidence
                results.extend(evidence)
            except Exception as exc:
                logger.warning("YouTube evidence fetch failed for %r: %s", topic, _redact(exc))
                self._quota.record_failure()

        return results

    def fetch_discovery_evidence(
        self,
        queries: list[str],
        published_after_hours: int = 48,
    ) -> list[SourceEvidence]:
        """Fetch discovery evidence using broad search queries.

        Uses quota; prioritizes queries in order given.
        Stops when quota exhausted rather than failing.
        """
        if not self.is_available:
            return []

        results: list[SourceEvidence] = []
        after_dt = datetime.now(timezone.utc) - timedelta(hours=published_after_hours)
        after_str = after_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        query_diag = self._diag()["discovery_queries"]

        for query in queries:
            if self._quota.is_exhausted:
                logger.info("YouTube quota exhausted; skipping remaining discovery queries.")
                break

            cache_key = f"discovery:{query.lower()}"
            if cache_key in self._evidence_cache:
                self._quota.record_cache_hit()
                results.extend(self._evidence_cache[cache_key])
                query_diag.append({
                    "query": query, "status": "cache_hit", "search_items": None,
                    "evidence_items": len(self._evidence_cache[cache_key]), "error": None,
                })
                continue

            if not self._quota.consume(1):
                logger.info("YouTube quota limit reached at query %r", query)
                break

            entry: dict[str, Any] = {
                "query": query, "status": "ok", "search_items": 0,
                "evidence_items": 0, "error": None,
            }
            query_diag.append(entry)
            self._diag()["last_search_error"] = None
            try:
                items = self._search_videos(
                    query,
                    published_after=after_str,
                    max_results=10,
                )
                entry["search_items"] = len(items)
                search_error = self._diag().get("last_search_error")
                if search_error:
                    entry["status"] = "search_failed"
                    entry["error"] = search_error
                evidence = self._process_search_results(query, items)
                entry["evidence_items"] = len(evidence)
                self._evidence_cache[cache_key] = evidence
                results.extend(evidence)
            except Exception as exc:
                logger.warning("Discovery search failed for %r: %s", query, _redact(exc))
                self._quota.record_failure()
                entry["status"] = "failed"
                entry["error"] = _error_summary(exc)

        recorded = {q["query"] for q in query_diag}
        for query in queries:
            if query not in recorded:
                query_diag.append({
                    "query": query, "status": "not_run_quota", "search_items": None,
                    "evidence_items": 0, "error": None,
                })

        return results

    def _search_videos(
        self,
        query: str,
        published_after: Optional[str] = None,
        max_results: int = 10,
    ) -> list[dict]:
        if not self._client:
            return []

        kwargs: dict[str, Any] = {
            "part": "id,snippet",
            "q": query,
            "type": "video",
            "order": "viewCount",
            "maxResults": min(max_results, 50),
            "relevanceLanguage": "en",
        }
        if published_after:
            kwargs["publishedAfter"] = published_after

        try:
            response = self._client.search().list(**kwargs).execute()
            return response.get("items", [])
        except Exception as exc:
            logger.warning("YouTube search API call failed: %s", _redact(exc))
            self._quota.record_failure()
            self._diag()["last_search_error"] = _error_summary(exc)
            return []

    def _process_search_results(
        self,
        topic: str,
        search_items: list[dict],
    ) -> list[SourceEvidence]:
        if not search_items:
            return []

        video_ids = [
            item["id"]["videoId"]
            for item in search_items
            if item.get("id", {}).get("videoId")
        ]
        if not video_ids:
            return []

        video_stats = self._fetch_video_stats(video_ids)
        channel_ids = list({
            vs["channel_id"]
            for vs in video_stats.values()
            if vs.get("channel_id")
        })
        channel_baselines = self._fetch_channel_baselines(channel_ids)

        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        results: list[SourceEvidence] = []

        for item in search_items:
            vid_id = item.get("id", {}).get("videoId")
            if not vid_id:
                continue

            snippet = item.get("snippet", {})
            stats = video_stats.get(vid_id, {})
            channel_id = stats.get("channel_id", snippet.get("channelId", ""))
            baseline = channel_baselines.get(channel_id, 0)
            views = stats.get("views", 0)
            rel_perf = (views / baseline) if baseline > 0 else 0.0

            pub_str = snippet.get("publishedAt", "")
            try:
                published_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                published_at = now

            age_hours = max(0.01, (now - published_at).total_seconds() / 3600)
            view_velocity = views / age_hours

            obs = Observation(
                observation_id=_obs_id(vid_id, today_str),
                source_type="youtube",
                topic_hint=topic,
                item_id=vid_id,
                channel_id=channel_id,
                observed_at=now.isoformat(),
                observed_views=views,
                channel_baseline=baseline,
                relative_performance=round(rel_perf, 3),
                extra={
                    "title": snippet.get("title", ""),
                    "view_velocity": round(view_velocity, 2),
                },
            )
            self._history.record(obs)

            results.append(SourceEvidence(
                topic_hint=topic,
                source_type="youtube",
                source_id=vid_id,
                observed_at=published_at,
                evidence_type="youtube_video",
                payload={
                    "video_id": vid_id,
                    "channel_id": channel_id,
                    "title": snippet.get("title", ""),
                    "views": views,
                    "channel_baseline_views": baseline,
                    "channel_upload_frequency_days": 7,
                    "observation_age_hours": round(age_hours, 1),
                    "relative_performance": round(rel_perf, 3),
                    "view_velocity": round(view_velocity, 2),
                    "tags": [],
                },
                base_confidence=0.80,
                is_independent=True,
            ))

        self._history.save()
        return results

    def _fetch_video_stats(self, video_ids: list[str]) -> dict[str, dict]:
        """Batch fetch video statistics (up to 50 per call)."""
        if not self._client or not video_ids:
            return {}

        result: dict[str, dict] = {}
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            try:
                resp = self._client.videos().list(
                    part="statistics,snippet",
                    id=",".join(batch),
                ).execute()
                for item in resp.get("items", []):
                    vid_id = item["id"]
                    stats = item.get("statistics", {})
                    snippet = item.get("snippet", {})
                    result[vid_id] = {
                        "views": int(stats.get("viewCount", 0)),
                        "channel_id": snippet.get("channelId", ""),
                    }
            except Exception as exc:
                logger.warning("Video stats batch failed: %s", _redact(exc))
                self._diag()["stats_failures"] += 1

        return result

    def _fetch_channel_baselines(self, channel_ids: list[str]) -> dict[str, int]:
        """Return per-channel view baselines, preferring historical observations."""
        if not channel_ids:
            return {}

        baselines: dict[str, int] = {}

        # Check observation history first (free)
        for ch_id in channel_ids:
            hist = self._history.get_by_channel(ch_id)
            recorded = [
                h["channel_baseline"]
                for h in hist
                if h.get("channel_baseline")
            ]
            if recorded:
                baselines[ch_id] = int(sum(recorded) / len(recorded))

        # Fetch missing from API
        missing = [cid for cid in channel_ids if cid not in baselines]
        if missing and self._client:
            for i in range(0, len(missing), 50):
                batch = missing[i : i + 50]
                try:
                    resp = self._client.channels().list(
                        part="statistics",
                        id=",".join(batch),
                    ).execute()
                    for item in resp.get("items", []):
                        ch_id = item["id"]
                        stats = item.get("statistics", {})
                        sub_count = int(stats.get("subscriberCount", 0))
                        # Rough estimate: ~2% of subscribers watch a typical video
                        baselines[ch_id] = max(1, int(sub_count * 0.02))
                except Exception as exc:
                    logger.warning("Channel stats batch failed: %s", _redact(exc))
                    self._diag()["stats_failures"] += 1

        return baselines
