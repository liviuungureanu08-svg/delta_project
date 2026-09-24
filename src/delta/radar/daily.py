"""Daily radar run entry point.

Usage:
    python -m delta.radar.daily
    python -m delta.radar.daily --verbose
    python -m delta.radar.daily --output-dir /path/to/output

One execution:
  1. Load configuration
  2. Collect live evidence (or fall back to offline mock providers)
  3. Autonomous topic discovery + clustering
  4. Run Stage 1 → Stage 2 → scoring → Top 5
  5. Persist observations and daily report
  6. Print human-readable summary
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from delta.config import radar_config
from delta.models.radar import DailyTop5
from delta.radar.discovery import TopicDiscovery
from delta.radar.history import ObservationHistory
from delta.radar.pipeline import RadarPipeline
from delta.radar.providers.base import RadarSourceProvider
from delta.radar.providers.news import MockNewsProvider
from delta.radar.providers.trends import MockTrendsProvider
from delta.radar.providers.youtube import MockYouTubeProvider
from delta.radar.quota import ProviderQuota

logger = logging.getLogger(__name__)


_DEFAULT_DISCOVERY_QUERIES: list[str] = [
    "new AI model release 2026",
    "AI coding tool",
    "large language model benchmark",
    "AI agent framework",
    "AI image video generation",
    "machine learning infrastructure",
    "AI startup funding",
    "Claude GPT Gemini Llama release",
    "AI developer tools 2026",
    "AI research breakthrough",
]

_FALLBACK_TOPICS: list[dict] = [
    {"topic": "Claude AI coding agent", "niche": "ai_tech"},
    {"topic": "AI video generation 2026", "niche": "ai_tech"},
    {"topic": "AI memory systems", "niche": "ai_tech"},
    {"topic": "AI image generation", "niche": "ai_tech"},
    {"topic": "global tariff impact small business", "niche": "cross_niche"},
]


def _configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _build_providers(
    cfg: dict,
    history: ObservationHistory,
) -> list[RadarSourceProvider]:
    """Build provider list from configuration and environment."""
    providers: list[RadarSourceProvider] = []
    live_cfg = cfg.get("live", {})
    use_live = live_cfg.get("enabled", False)

    if use_live:
        # YouTube (live)
        youtube_key = os.environ.get("YOUTUBE_API_KEY", "")
        if youtube_key:
            try:
                from delta.radar.providers.live_youtube import LiveYouTubeProvider

                yt_cfg = live_cfg.get("youtube", {})
                quota = ProviderQuota(
                    provider_name="youtube_live",
                    daily_budget=yt_cfg.get(
                        "daily_search_budget", LiveYouTubeProvider.DEFAULT_DAILY_SEARCH_BUDGET
                    ),
                )
                providers.append(
                    LiveYouTubeProvider(
                        api_key=youtube_key,
                        quota=quota,
                        history=history,
                        config=yt_cfg,
                    )
                )
                logger.info("Live YouTube provider enabled.")
            except Exception as exc:
                logger.warning("Live YouTube provider init failed: %s — using mock.", exc)
                providers.append(MockYouTubeProvider())
        else:
            logger.info("YOUTUBE_API_KEY not set — using mock YouTube provider.")
            providers.append(MockYouTubeProvider())

        # News (live RSS)
        try:
            from delta.radar.providers.live_news import LiveNewsProvider

            news_cfg = live_cfg.get("news", {})
            providers.append(
                LiveNewsProvider(
                    feeds=news_cfg.get("feeds"),
                    max_age_hours=news_cfg.get("max_age_hours", 72),
                )
            )
            logger.info("Live news provider enabled.")
        except Exception as exc:
            logger.warning("Live news provider init failed: %s — using mock.", exc)
            providers.append(MockNewsProvider())

        # Search interest: disabled in Phase 3
        from delta.radar.providers.search_interest import SearchInterestProvider

        providers.append(SearchInterestProvider(enabled=False))

    else:
        logger.info("Live providers disabled — using offline mock providers.")
        providers.extend([MockYouTubeProvider(), MockTrendsProvider(), MockNewsProvider()])

    return providers


def _collect_discovery_evidence(
    providers: list[RadarSourceProvider],
    discovery_queries: list[str],
) -> list:
    """Collect raw evidence for autonomous topic discovery."""
    from delta.radar.providers.live_news import LiveNewsProvider
    from delta.radar.providers.live_youtube import LiveYouTubeProvider

    all_evidence = []
    for provider in providers:
        if isinstance(provider, LiveYouTubeProvider) and provider.is_available:
            ev = provider.fetch_discovery_evidence(
                queries=discovery_queries,
                published_after_hours=48,
            )
            all_evidence.extend(ev)
        elif isinstance(provider, LiveNewsProvider):
            ev = provider.fetch_discovery_evidence()
            all_evidence.extend(ev)
    return all_evidence


def _build_diagnostics(
    cfg: dict,
    providers: list[RadarSourceProvider],
    discovery_evidence: list,
    discovery_mode: str,
    cluster_count: int,
    candidate_diagnostics: list[dict],
) -> dict:
    """Assemble key-free runtime diagnostics for the JSON report."""
    from delta.radar.providers.live_news import LiveNewsProvider
    from delta.radar.providers.live_youtube import LiveYouTubeProvider

    youtube: dict = {"provider": "none", "provider_initialized": False}
    news: dict = {"provider": "none"}
    for provider in providers:
        if isinstance(provider, LiveYouTubeProvider):
            youtube = provider.diagnostics()
        elif isinstance(provider, MockYouTubeProvider):
            youtube = {
                "provider": "mock",
                "provider_initialized": False,
                "youtube_api_key_set": bool(os.environ.get("YOUTUBE_API_KEY")),
            }
        elif isinstance(provider, LiveNewsProvider):
            news = provider.diagnostics()
        elif isinstance(provider, MockNewsProvider):
            news = {"provider": "mock"}

    by_type: dict[str, int] = {}
    for ev in discovery_evidence:
        by_type[ev.source_type] = by_type.get(ev.source_type, 0) + 1
    youtube["total_fresh_evidence"] = by_type.get("youtube", 0)
    news["total_fresh_evidence"] = by_type.get("news", 0)

    return {
        "live_enabled": bool(cfg.get("live", {}).get("enabled", False)),
        "discovery_mode": discovery_mode,
        "discovery_evidence_by_source_type": by_type,
        "discovery_cluster_count": cluster_count,
        "youtube": youtube,
        "rss": news,
        "candidates": candidate_diagnostics,
    }


def _format_report(top5: DailyTop5, run_date: str) -> str:
    lines = [
        f"=== DELTA DAILY RADAR — {run_date} ===",
        f"Candidates evaluated : {top5.candidates_evaluated}",
        f"Candidates rejected  : {top5.candidates_rejected}",
        f"Opportunities found  : {len(top5.reports)}",
        "",
    ]

    if not top5.reports:
        lines.append("No opportunities reached TOP_5 threshold today.")
        return "\n".join(lines)

    for i, r in enumerate(top5.reports, 1):
        lines += [
            f"--- #{i} {r.topic.upper()} ---",
            f"  Niche        : {r.niche}",
            f"  Opp. Score   : {r.opportunity_score:.3f}",
            f"  Conf. Score  : {r.confidence_score:.3f}",
            f"  Momentum     : {r.momentum_state.value}",
            f"  Saturation   : {r.saturation_state.value}",
            f"  Why Now      : {r.why_now}",
            f"  Evidence     : {r.strongest_evidence}",
            f"  Risk         : {r.main_risk}",
            f"  Formats      : {', '.join(r.recommended_formats)}",
            f"  Angle        : {r.suggested_angle}",
            f"  Approval     : {'PENDING' if r.human_approved is None else r.human_approved}",
            "",
        ]

    lines.append("All opportunities require human approval before production.")
    return "\n".join(lines)


def run_daily(
    output_dir: str = "data/reports",
    offline_fallback_topics: Optional[list[dict]] = None,
    discovery_queries: Optional[list[str]] = None,
    verbose: bool = False,
) -> DailyTop5:
    """Execute a full daily radar run.

    Returns the DailyTop5 result (all reports pending human_approved = None).
    Writes JSON + text report to output_dir.
    """
    _configure_logging(verbose)
    cfg = radar_config()["radar"]
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    history = ObservationHistory()
    providers = _build_providers(cfg, history)
    pipeline = RadarPipeline(cfg)
    discovery = TopicDiscovery()
    queries = discovery_queries or _DEFAULT_DISCOVERY_QUERIES

    # --- Autonomous discovery from live sources ---
    discovery_evidence = _collect_discovery_evidence(providers, queries)

    cluster_count = 0
    if discovery_evidence:
        discovery_mode = "live"
        clusters = discovery.discover(discovery_evidence)
        cluster_count = len(clusters)
        topic_inputs = discovery.to_topic_inputs(clusters, min_evidence=1)
        logger.info("Discovered %d topic cluster(s) from live evidence.", len(clusters))
    else:
        discovery_mode = "fallback_topics"
        topic_inputs = offline_fallback_topics or _FALLBACK_TOPICS
        logger.info(
            "No live discovery evidence — using fallback topics (%d).", len(topic_inputs)
        )

    # --- Run pipeline (Stage 1 → Stage 2 → scoring → Top 5) ---
    top5 = pipeline.run(topic_inputs, providers)

    # --- Persist reports ---
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    report_path = Path(output_dir) / f"report_{run_date}.json"
    machine_data = {
        "generated_at": top5.generated_at.isoformat(),
        "run_date": run_date,
        "candidates_evaluated": top5.candidates_evaluated,
        "candidates_rejected": top5.candidates_rejected,
        "opportunities": [r.to_dict() for r in top5.reports],
        "diagnostics": _build_diagnostics(
            cfg,
            providers,
            discovery_evidence,
            discovery_mode,
            cluster_count,
            pipeline.last_candidate_diagnostics,
        ),
    }
    with open(report_path, "w") as f:
        json.dump(machine_data, f, indent=2, default=str)

    human_report = _format_report(top5, run_date)
    human_path = Path(output_dir) / f"report_{run_date}.txt"
    with open(human_path, "w") as f:
        f.write(human_report)

    print(human_report)
    logger.info("Reports saved: %s", report_path)

    return top5


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Delta daily radar run")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--output-dir", default="data/reports")
    args = parser.parse_args()
    run_daily(output_dir=args.output_dir, verbose=args.verbose)
