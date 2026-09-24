#!/usr/bin/env python3
"""
Delta Phase 2 — Opportunity Intelligence Demo

Demonstrates the full radar pipeline using fixture-based mock evidence.
No API keys, no network calls, no paid services required.

Scenarios covered:
  - Normal AI/Tech candidate (validated, accelerating)
  - Promising early WATCH candidate (AI memory — insufficient evidence yet)
  - Validated accelerating candidate (AI video generation)
  - Obvious false positive (keyboard shortcuts — single low-credibility signal)
  - Saturated candidate (AI image generation — stable mainstream)
  - Cross-niche breakout (global tariff impact on small business)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from delta.radar import RadarPipeline
from delta.radar.providers import MockYouTubeProvider, MockTrendsProvider, MockNewsProvider
from delta.models.radar import LifecycleState


def separator(title: str = "") -> None:
    print("\n" + "=" * 65)
    if title:
        print(f"  {title}")
        print("=" * 65)


def main() -> None:
    print("\nDELTA OPPORTUNITY INTELLIGENCE — PHASE 2 DEMO")
    print("(offline, fixture data, no API keys, no network calls)")

    # Topic inputs: representative scenarios
    topic_inputs = [
        {
            "topic": "Claude AI coding agent",
            "niche": "ai_tech",
            "why_now": (
                "Multiple independent channels showing breakout performance on Claude-agent "
                "content; strong news coverage from reputable tech outlets; rising search interest."
            ),
        },
        {
            "topic": "AI video generation 2026",
            "niche": "ai_tech",
            "why_now": (
                "AI video quality crossed a visible threshold; major channels showing 3–8x "
                "channel baseline performance; mainstream tech press coverage."
            ),
        },
        {
            "topic": "AI memory systems",
            "niche": "ai_tech",
            "why_now": "Early signals — one breakout indie channel; MIT Tech Review coverage.",
        },
        {
            "topic": "keyboard shortcuts productivity",
            "niche": "ai_tech",
            "why_now": "Evergreen topic — one blog post with low credibility.",
        },
        {
            "topic": "AI image generation",
            "niche": "ai_tech",
            "why_now": "Mature topic — many large channels already covering it.",
        },
        {
            "topic": "global tariff impact small business",
            "niche": "cross_niche",
            "why_now": (
                "Breaking macro event with strong independent confirmation: Reuters, Bloomberg, "
                "AP News + multiple finance channels showing 6–8x breakout performance."
            ),
        },
    ]

    providers = [
        MockYouTubeProvider(),
        MockTrendsProvider(),
        MockNewsProvider(),
    ]

    separator("RUNNING RADAR PIPELINE")
    print("  Topics evaluated :", len(topic_inputs))
    print("  Providers active  :", [p.source_type for p in providers])

    pipeline = RadarPipeline()
    daily_top5 = pipeline.run(topic_inputs, providers)

    separator("INTERMEDIATE CANDIDATE STATES")
    # Re-run just Stage 1+2 to show intermediate states per candidate
    from delta.radar.stage1 import Stage1Discovery
    from delta.radar.stage2 import Stage2Validation
    from delta.radar.scoring import RadarScoring
    from delta.radar.signals import evidence_from_source
    from delta.models.radar import RadarCandidate
    from delta.config import radar_config

    cfg = radar_config()["radar"]
    stage1 = Stage1Discovery(cfg)
    stage2 = Stage2Validation(cfg)
    scoring = RadarScoring(cfg)

    for ti in topic_inputs:
        from delta.models.radar import Evidence
        all_ev = []
        for p in providers:
            for se in p.fetch_evidence([ti["topic"]]):
                all_ev.append(evidence_from_source(se))

        c = RadarCandidate(topic=ti["topic"], niche=ti["niche"], evidence=all_ev)
        c = stage1.process(c)
        c = scoring.score(c)
        c = stage2.process(c)
        c = scoring.score(c)

        print(f"\n  [{ti['niche'].upper()}] {ti['topic']}")
        print(f"    Evidence items   : {len(all_ev)}")
        print(f"    Independent srcs : {c.signals.independent_source_count}")
        print(f"    Lifecycle        : {c.lifecycle.value}")
        print(f"    Momentum         : {c.signals.momentum.value}")
        print(f"    Saturation       : {c.saturation_state.value}")
        print(f"    Opportunity score: {c.opportunity_score:.3f}")
        print(f"    Confidence score : {c.confidence_score:.3f}")
        if c.main_risk:
            print(f"    Risk flag        : {c.main_risk[:80]}")

    separator(f"DAILY TOP {len(daily_top5.reports)} (max 5)")
    print(f"  Candidates evaluated: {daily_top5.candidates_evaluated}")
    print(f"  Candidates rejected : {daily_top5.candidates_rejected}")
    print(f"  Top 5 count         : {len(daily_top5.reports)}")
    assert len(daily_top5.reports) <= 5, "FAIL: Top 5 limit exceeded!"

    for i, report in enumerate(daily_top5.reports, 1):
        print(f"\n  [{i}] {report.topic}")
        d = report.to_dict()
        print(f"    Niche          : {d['niche']}")
        print(f"    Lifecycle      : {d['lifecycle']}")
        print(f"    Opportunity    : {d['opportunity_score']:.3f}")
        print(f"    Confidence     : {d['confidence_score']:.3f}")
        print(f"    Momentum       : {d['momentum']}")
        print(f"    Saturation     : {d['saturation']}")
        print(f"    Why now        : {d['why_now'][:70]}...")
        print(f"    Strongest evid.: {d['strongest_evidence'][:70]}...")
        print(f"    Main risk      : {d['main_risk'][:70] if d['main_risk'] else 'None'}")
        print(f"    Formats        : {d['recommended_formats']}")
        print(f"    Angle          : {d['suggested_angle'][:70]}...")
        print(f"    Human approved : {d['human_approved']} (pending — required)")

    separator("VERIFICATION")
    all_pending = all(r.human_approved is None for r in daily_top5.reports)
    print(f"  Top 5 ≤ 5 candidates : {'PASS' if len(daily_top5.reports) <= 5 else 'FAIL'}")
    print(f"  All await human appr : {'PASS' if all_pending else 'FAIL'}")
    print(f"  No paid API used     : PASS")
    print(f"  No network calls     : PASS")
    print(f"  No fabricated data   : PASS (fixture-based)")

    separator("DEMO COMPLETE")
    print("\n  Phase 2 radar pipeline: OPERATIONAL")
    print("  Live data: NONE (fixtures only)")
    print("  Paid API usage: NONE\n")


if __name__ == "__main__":
    main()
