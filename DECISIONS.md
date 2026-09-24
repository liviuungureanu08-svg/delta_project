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
