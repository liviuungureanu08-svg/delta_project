# PROJECT STATE

## Purpose
AI-assisted faceless content production system for YouTube and Instagram (AI/Tech niche).

## Current Phase
**Phase 2 — Opportunity Intelligence Engine ("Trend Radar")** (complete)

## Package
`delta` (renamed from `kronos` in Phase 2)

## Architecture

```
config/
  channel.yaml         Channel strategy, budgets, provider settings
  radar.yaml           Radar pipeline thresholds (Stage 1, Stage 2, scoring weights, Top 5)
src/delta/
  models/
    topic.py           TopicCandidate (opportunity + scoring fields)
    research.py        MasterResearch
    content_plan.py    ContentPlan + ContentSection + ApprovalStatus
    retention.py       RetentionPlan + TimelineSegment + AssetType enum
    budget.py          ProductionBudget + AssetCost
    radar.py           RadarCandidate, Evidence, Signals, SaturationState,
                       LifecycleState, MomentumState, OpportunityReport, DailyTop5
  engine/
    opportunity.py     Deterministic scoring engine (qualitative signals, configurable weights)
    planner.py         ContentPlanner
    retention.py       RetentionBuilder
    cost.py            CostController
  providers/
    base.py            Abstract interfaces: VideoProvider, ImageProvider, TTSProvider
    mock.py            Mock implementations
  radar/
    providers/
      base.py          RadarSourceProvider + SourceEvidence (abstract signal provider)
      youtube.py       MockYouTubeProvider (fixture-based, offline)
      trends.py        MockTrendsProvider (fixture-based, offline)
      news.py          MockNewsProvider (fixture-based, offline)
      __init__.py      Re-exports all three mock providers
    signals.py         SignalNormalizer (SourceEvidence → Evidence → Signals)
    saturation.py      SaturationClassifier (upload velocity + large-channel escalation)
    stage1.py          Stage1Discovery (recall-first: DISCOVERED → WATCH)
    stage2.py          Stage2Validation (skeptical: WATCH → VALIDATED or stays WATCH)
    scoring.py         RadarScoring (opportunity score + confidence score, separate)
    top5.py            Top5Selector (VALIDATED → TOP_5 → HUMAN_APPROVAL, max 5)
    pipeline.py        RadarPipeline (orchestrator: topics + providers → DailyTop5)
    __init__.py        Re-exports RadarPipeline
  workflow/
    gates.py           ApprovalGate
  config.py            Cached YAML config loaders (channel + radar)
demo/
  run_demo.py          Phase 1 offline demo
  run_phase2_demo.py   Phase 2 radar pipeline demo (6 topics, offline, no credentials)
  mock_data.py         Phase 1 mock data
tests/                 116 tests (Phase 1: 43, Phase 2: 73)
```

## Candidate Lifecycle
```
DISCOVERED → WATCH → VALIDATED → TOP_5 → HUMAN_APPROVAL
                                         └→ REJECTED
```

## Saturation States
`EARLY → EMERGING → ACCELERATING → MAINSTREAM → SATURATED`
Classified from estimated upload velocity (channel count × upload frequency) and escalated if large-channel coverage is high. Config-driven thresholds.

## Important Constraints
- No real API calls — all providers are fixture-based (offline, no credentials)
- No fabricated real-world analytics
- Human approval required for all final decisions (human_approved always None until human acts)
- DailyTop5 enforces max 5 candidates at object construction (ValueError if exceeded)
- Opportunity score and confidence score are always separate — never collapsed
- All thresholds configurable in config/radar.yaml
- Pure Python + PyYAML; no external service dependencies

## Completed Work
**Phase 1:**
- Channel/budget/provider/scoring/retention configuration (YAML)
- All Phase 1 data models
- Opportunity scoring engine, content planner, retention builder, cost controller
- Provider abstraction + mock implementations
- Approval gate system
- Mock end-to-end demo + unit tests

**Phase 2:**
- Package renamed: `kronos` → `delta` (all imports, tests, demo, docs)
- Radar data models (Evidence, Signals, RadarCandidate, DailyTop5, OpportunityReport)
- Signal provider abstraction + three offline mock providers (YouTube, Trends, News)
- SignalNormalizer + SaturationClassifier
- Stage 1 (recall-first discovery) + Stage 2 (skeptical validation with false-positive guards)
- Dual scoring engine (opportunity score and confidence score, separate)
- Top 5 selector with HUMAN_APPROVAL lifecycle
- RadarPipeline orchestrator
- Phase 2 offline demo (6 topic scenarios including WATCH, false positive, cross-niche)
- 73 new Phase 2 tests (evidence, signals, saturation, stage1, stage2, scoring, top5, pipeline, migration)

## Known Limitations
- Phase 1: Scoring uses qualitative signals only; no real search/analytics data
- Phase 2: All radar providers are fixture-based; real Google Trends / YouTube Data API / news RSS integration is Phase 3
- SaturationClassifier estimates upload velocity from channel metadata, not from actual video counts
- Top 5 scoring and formatting is deterministic but not yet A/B tested against real audience behavior
- Cross-niche thresholds (3 independent sources, 48h window) chosen conservatively; may need calibration

## Next Logical Task
**Phase 3 — Live Signal Integration**: Replace MockYouTubeProvider/MockTrendsProvider/MockNewsProvider with real API clients (YouTube Data API v3, SerpAPI/PyTrends, RSS feed aggregator). Implement the same RadarSourceProvider interface. No other pipeline changes required.
