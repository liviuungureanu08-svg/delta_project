# PROJECT STATE

## Purpose
AI-assisted faceless content production system for YouTube and Instagram (AI/Tech niche).

## Current Phase
**Phase 1 — Foundation** (complete)

## Architecture

```
config/              YAML-driven configuration (channel, budgets, providers, scoring, retention)
src/kronos/
  models/            Pure data classes — no external dependencies
    topic.py         TopicCandidate (opportunity + scoring fields)
    research.py      MasterResearch (one research → many formats)
    content_plan.py  ContentPlan + ContentSection + ApprovalStatus
    retention.py     RetentionPlan + TimelineSegment + AssetType enum
    budget.py        ProductionBudget + AssetCost
  engine/
    opportunity.py   Deterministic scoring engine (config-weighted, qualitative signals)
    planner.py       ContentPlanner (approved candidate + research → ContentPlan)
    retention.py     RetentionBuilder (ContentPlan → RetentionPlan with timeline)
    cost.py          CostController (RetentionPlan → ProductionBudget)
  providers/
    base.py          Abstract interfaces: VideoProvider, ImageProvider, TTSProvider
    mock.py          Mock implementations (no API calls, zero cost)
  workflow/
    gates.py         ApprovalGate for TOPIC/SCRIPT/PRODUCTION/PUBLISH steps
  config.py          Cached YAML config loader
demo/                Offline end-to-end mock workflow
tests/               Unit tests (config, opportunity, approval, content plan, retention, cost, providers)
```

## Important Constraints
- No real API calls in Phase 1 — mock providers only
- No secrets or credentials committed
- Provider pricing is configuration-driven, not hard-coded
- Scoring weights are configurable
- All approval gates default to human; "auto" is an opt-in config change
- Portability: pure Python + PyYAML only

## Completed Work
- Channel/budget/provider/scoring/retention configuration (YAML)
- All Phase 1 data models
- Opportunity scoring engine
- Content planner (SHORT, UTILITY_LONG_FORM, DOCUMENTARY, INSTAGRAM_POST, INSTAGRAM_CAROUSEL)
- Retention plan builder with configurable pacing
- Cost controller
- Provider abstraction + mock implementations
- Approval gate system (4 gates, all human by default)
- Mock end-to-end demo
- Unit tests (35 tests across 6 test modules)
- README, PROJECT_STATE.md, DECISIONS.md

## Known Limitations
- Scoring uses qualitative signals only; no real search/analytics data
- RetentionBuilder generates uniform pacing segments; future versions should follow section structure
- ContentPlanner section durations for DOCUMENTARY/long-form are approximations

## Next Logical Task
**Phase 2 — Research Integration**: Connect a real data source (YouTube Trending API, Google Trends, or RSS news feed) to populate TopicCandidates with verified demand signals, replacing mock data.
