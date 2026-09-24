# PROJECT STATE

## Purpose
AI-assisted faceless content production system for YouTube and Instagram (AI/Tech niche).

## Current Phase
**Phase 3 — Live Signal Integration & Autonomous Discovery** (complete)

## Package
`delta` (renamed from `kronos` in Phase 2)

## Architecture

```
config/
  channel.yaml         Channel strategy, budgets, provider settings
  radar.yaml           Radar pipeline thresholds + Phase 3 live source config
src/delta/
  models/
    topic.py           TopicCandidate
    research.py        MasterResearch
    content_plan.py    ContentPlan + ContentSection + ApprovalStatus
    retention.py       RetentionPlan + TimelineSegment + AssetType
    budget.py          ProductionBudget + AssetCost
    radar.py           RadarCandidate, Evidence, Signals, SaturationState,
                       LifecycleState, MomentumState, OpportunityReport, DailyTop5
  engine/
    opportunity.py     Deterministic scoring engine
    planner.py         ContentPlanner
    retention.py       RetentionBuilder
    cost.py            CostController
  providers/
    base.py            Abstract interfaces: VideoProvider, ImageProvider, TTSProvider
    mock.py            Mock implementations
  radar/
    providers/
      base.py          RadarSourceProvider + SourceEvidence (abstract interface)
      youtube.py       MockYouTubeProvider (fixture-based, offline)
      trends.py        MockTrendsProvider (fixture-based, offline)
      news.py          MockNewsProvider (fixture-based, offline)
      live_youtube.py  LiveYouTubeProvider (YouTube Data API v3, requires YOUTUBE_API_KEY)
      live_news.py     LiveNewsProvider (multi-source RSS/feedparser)
      search_interest.py SearchInterestProvider (interface + disabled state, Phase 3)
      __init__.py      Re-exports all providers
    quota.py           ProviderQuota (daily budget tracking, cache hit / failure tracking)
    history.py         ObservationHistory (JSON-backed local persistence for trend comparison)
    discovery.py       TopicDiscovery (autonomous topic clustering from raw evidence)
    signals.py         SignalNormalizer
    saturation.py      SaturationClassifier
    stage1.py          Stage1Discovery (DISCOVERED → WATCH)
    stage2.py          Stage2Validation (WATCH → VALIDATED)
    scoring.py         RadarScoring (opportunity score + confidence score, separate)
    top5.py            Top5Selector (VALIDATED → TOP_5 → HUMAN_APPROVAL, max 5)
    pipeline.py        RadarPipeline (orchestrator)
    daily.py           Daily run entry point (python -m delta.radar.daily)
    __init__.py        Re-exports RadarPipeline
  workflow/
    gates.py           ApprovalGate
  config.py            Cached YAML config loaders
demo/
  run_demo.py          Phase 1 offline demo
  run_phase2_demo.py   Phase 2 offline demo
  mock_data.py         Phase 1 mock data
tests/                 186 tests (Phase 1: 43, Phase 2: 73, Phase 3: 70)
.env.example           Variable NAMES only, no credentials
```

## Candidate Lifecycle
```
DISCOVERED → WATCH → VALIDATED → TOP_5 → HUMAN_APPROVAL
                                         └→ REJECTED
```

## Phase 3 Architecture

### Autonomous Discovery Flow
```
LIVE SOURCES (YouTube API / RSS)
↓
RAW ITEMS (SourceEvidence)
↓
NORMALIZATION (word-overlap, Jaccard similarity)
↓
TOPIC CLUSTERING (TopicDiscovery)
↓
DEDUPLICATION (source_id based)
↓
STAGE 1 → STAGE 2 → SCORING → TOP 5 → HUMAN APPROVAL
```

### Live Providers
- **LiveYouTubeProvider**: YouTube Data API v3. Requires YOUTUBE_API_KEY env var.
  - Discovery via configurable keyword searches
  - Channel-relative performance (views / channel_baseline_views)
  - Historical baselines from ObservationHistory, estimated from subscriber count when absent
  - Evidence cache: second fetch of same query costs zero quota
  - Quota: configurable daily_search_budget (default 50 search requests)
  - Graceful degradation: falls back to MockYouTubeProvider if key absent
- **LiveNewsProvider**: Multi-source RSS via feedparser.
  - 8 default reputable feeds (TechCrunch, Wired, Ars Technica, The Verge, Reuters, etc.)
  - Configurable feed list via radar.yaml
  - Per-feed socket timeout (default 10s)
  - One feed failure does not affect others
  - fetch_evidence(): topic-matched articles
  - fetch_discovery_evidence(): all fresh articles for autonomous discovery
- **SearchInterestProvider**: DISABLED in Phase 3.
  - Interface preserved for future official integration
  - No PyTrends (fragile scraping), no SerpAPI (paid)

### Quota Controls
- ProviderQuota tracks: requests_made, remaining, cache_hits, failed_requests, available
- YouTube: configurable daily_search_budget (search request count)
- News: configurable per-feed call budget
- Quota priority order: WATCH candidates → high-potential → primary AI/Tech → cross-niche

### Observation History
- JSON-backed local store at data/observations/observations.json
- Stores: source item ID, topic hint, channel ID, observed timestamp, views, baseline, relative performance
- Enables channel baseline computation from historical data
- data/ directory is gitignored (runtime data)

### Daily Run
```
python -m delta.radar.daily [--verbose] [--output-dir PATH]
```
Writes: data/reports/report_YYYY-MM-DD.json + .txt

## Completed Work
**Phase 1:** Channel/budget/scoring configuration, data models, engines, mock providers, demo + tests.
**Phase 2:** Package rename, radar models, mock providers, SignalNormalizer, SaturationClassifier,
Stage 1/2, dual scoring engine, Top5Selector, RadarPipeline, demo + 73 tests.
**Phase 3:**
- LiveYouTubeProvider (YouTube Data API v3)
- LiveNewsProvider (multi-source RSS/feedparser)
- SearchInterestProvider (disabled interface)
- TopicDiscovery (autonomous clustering, no LLM dependency)
- ObservationHistory (JSON persistence)
- ProviderQuota (budget tracking)
- Daily run entry point (python -m delta.radar.daily)
- Updated radar.yaml with live source configuration
- .env.example (variable names only)
- .gitignore updated (data/ excluded)
- requirements.txt updated (feedparser, google-api-python-client)
- 70 new Phase 3 tests (186 total)

## Live Source Status
| Source               | Status                              |
|----------------------|-------------------------------------|
| YouTube Data API v3  | IMPLEMENTED — requires YOUTUBE_API_KEY |
| RSS / News feeds     | IMPLEMENTED — no credentials needed |
| Search Interest      | INTERFACE ONLY — disabled Phase 3   |

## Important Constraints
- Human approval required for all final decisions (human_approved always None until human acts)
- DailyTop5 enforces max 5 candidates at construction (ValueError if exceeded)
- Opportunity score and confidence score always separate — never collapsed (D6)
- Credentials only through environment variables — never committed or logged
- All thresholds configurable in config/radar.yaml
- Provider failures degrade gracefully (fall back to mock or empty evidence)
- Mock providers always available for offline dev, tests, fallback
- No paid APIs required; no scraping

## Known Limitations
- Channel upload_frequency_days defaults to 7 in live YouTube provider (not queried from API)
- YouTube channel baselines estimated from ~2% of subscriber count when no history exists
- Search interest (Google Trends) not integrated — no official free API available
- RSS feed timestamps depend on feed quality; some feeds may have missing/stale publish dates
- Discovery clustering uses word-overlap Jaccard — semantic similarity requires optional LLM layer

## Next Logical Task
**Phase 4 — Scheduling & Monitoring**: Cloud scheduling (Airflow / cron), Slack/email report
delivery, human approval workflow, expanded reference channel list, YouTube channel analytics
for real upload frequency tracking.
