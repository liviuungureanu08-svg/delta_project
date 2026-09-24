# Kronos AI Content Factory — Phase 1

AI-assisted faceless content production system for YouTube and Instagram.

## Purpose

Kronos automates the **planning** phase of content production: discovering opportunities, evaluating topics, structuring research, planning multi-format content, designing retention timelines, and estimating production costs — before any video is generated or published.

## Phase 1 Architecture

```
config/              Channel, budget, provider, scoring, retention config
src/kronos/
  models/            Data models: TopicCandidate, MasterResearch, ContentPlan,
                     RetentionPlan, ProductionBudget
  engine/            OpportunityEngine, ContentPlanner, RetentionBuilder, CostController
  providers/         Abstract provider interfaces + mock implementations
  workflow/          Approval gates (TOPIC / SCRIPT / PRODUCTION / PUBLISH)
  config.py          Config loader
demo/                Offline mock end-to-end workflow demo
tests/               Focused unit tests
```

One researched topic produces multiple content formats (Shorts, long-form, Instagram, documentary) from shared `MasterResearch`.

## Setup

```bash
pip install -r requirements.txt
# or: pip install -e .
```

Python 3.10+ required.

## Run the demo

```bash
cd demo
python run_demo.py
```

No API keys, no network calls, no paid services needed.

## Run tests

```bash
pytest
```

## What Phase 1 does NOT implement

- Live market research / YouTube / Instagram API
- Any real video, image, or TTS generation
- Automated rendering or publishing
- Analytics collection or performance learning
- Full script generation
- Frontend or dashboard
- Monetization predictions
- Real provider API calls (Higgsfield, ElevenLabs, etc.)

These belong to later phases.
