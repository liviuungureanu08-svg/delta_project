# DECISIONS

## D1 — Config-driven, not code-driven
Channel strategy, budgets, scoring weights, pacing rules, and provider pricing live in YAML. Business logic never hard-codes these values. Rationale: the channel strategy will change frequently; requiring code changes would be a friction tax on iteration.

## D2 — Qualitative scoring only in Phase 1
OpportunityEngine scores from qualitative strings ("rising", "high", "low") rather than fabricating numeric data. Real search volumes and analytics remain unknown until live integrations exist. Rationale: fabricating statistics would produce unreliable decisions and mislead future modules.

## D3 — One MasterResearch → many formats
Research is not duplicated per format. ContentPlanner draws from a shared MasterResearch object. Rationale: reduces research cost and ensures consistency across assets derived from the same topic.

## D4 — Provider abstraction before any real provider
Business logic depends only on abstract interfaces (VideoProvider, ImageProvider, TTSProvider). Mock implementations satisfy Phase 1. Rationale: prevents coupling to any specific vendor and enables local/cloud provider switching later without touching planning code.

## D5 — Human approval default, auto as opt-in
All four approval gates default to human. Setting a gate to "auto" in channel.yaml is the only supported bypass. Rationale: autonomous publishing carries financial and brand risk; automation should be opted into explicitly, not accidentally.

## D6 — Separate opportunity score and confidence score (never collapse)
RadarCandidate carries `opportunity_score` (how large/timely the opportunity is) and `confidence_score` (how reliably the signals confirm it) as distinct floats. No combined score is computed. Rationale: a high-opportunity, low-confidence candidate must be representable and treated differently from a high-confidence, moderate-opportunity candidate. Collapsing would destroy information.

## D7 — Two-stage radar: recall-first Stage 1, skeptical Stage 2
Stage 1 (discovery) has low thresholds and favors recall — it promotes to WATCH on minimal evidence to avoid missing early signals. Stage 2 (validation) is skeptical — it requires multiple independent source types, fresh evidence within niche-specific time windows, and a minimum opportunity score before promoting to VALIDATED. Rationale: a missed real opportunity costs more than a false positive held at WATCH; the human approval gate catches anything Stage 2 passes through.

## D8 — YouTube signals are channel-relative, not absolute
YouTube evidence is scored by `views / channel_baseline_views` (relative performance multiplier), not raw view count. A 50k-view video on a 5k-baseline channel (10x) is a stronger signal than a 500k-view video on a 450k-baseline channel (1.1x). Rationale: absolute view counts conflate channel size with topic momentum; relative performance isolates the signal.

## D9 — Evidence independence by source_id deduplication
When counting independent sources for Stage 2 validation, evidence items with duplicate `source_id` are collapsed to one. `is_independent=True` is required; evidence from the same provider batch share a source_type but different source_ids. Rationale: corroboration from distinct sources (YouTube + trends + news) is fundamentally different from multiple signals from the same source.

## D10 — Cross-niche requires stricter thresholds than primary niche
Topics tagged `cross_niche` require 3 independent sources (vs 2 for `ai_tech`), a shorter evidence age window (48h vs 72h), and a higher minimum confidence (0.70 vs 0.55). Rationale: content that crosses out of the channel's primary niche carries higher audience-mismatch risk; the stronger evidence requirement partially compensates for the lack of niche-fit confidence.

## D11 — DailyTop5 enforces its own invariant at construction
`DailyTop5.__post_init__` raises `ValueError` if more than 5 reports are provided. The Top5Selector also enforces this before construction. Rationale: the "Top 5" constraint is a product guarantee, not a convention; a double-enforcement means it cannot be violated by future code that bypasses the selector.

## D12 — All radar providers are offline and fixture-based for Phase 2
MockYouTubeProvider, MockTrendsProvider, and MockNewsProvider use hard-coded fixture dicts — no network calls, no API keys, no credentials. The RadarSourceProvider interface is designed so real API clients can replace them transparently in Phase 3. Rationale: Phase 2 validates pipeline architecture and scoring without incurring API costs or requiring credentials from contributors.

## D13 — Saturation is estimated, not measured
SaturationClassifier estimates upload velocity from channel upload_frequency_days × the count of channels that have produced content on the topic, then escalates one step if large-channel coverage is high. It does not query YouTube's actual video count. Rationale: a precise video count requires an API call; an estimate from fixture metadata is sufficient to distinguish EARLY from SATURATED for editorial decisions, and it scales to real providers when they supply the same fields.
