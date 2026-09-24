#!/usr/bin/env python3
"""
Kronos Phase 1 — Mock End-to-End Workflow Demo

Demonstrates the complete planning pipeline using mock data only.
No API keys, no network calls, no paid services required.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kronos.engine import ContentPlanner, CostController, OpportunityEngine, RetentionBuilder
from kronos.workflow import ApprovalGate, WorkflowState
from kronos.models.content_plan import ApprovalStatus

from mock_data import make_master_research, make_topic_candidate


def separator(title: str = "") -> None:
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


def demo_approval_gate(subject: str, context: str) -> bool:
    """Simulates a human approving in the demo."""
    print(f"\n[GATE]")
    print(f"  Subject : {subject}")
    print(f"  Context : {context[:80]}...")
    decision = True  # auto-approve in demo
    print(f"  Decision: {'APPROVED' if decision else 'REJECTED'} (demo auto-approve)")
    return decision


def main() -> None:
    print("\nKRONOS AI CONTENT FACTORY — PHASE 1 DEMO")
    print("(offline, mock data, no API keys)")

    # ── Step 1: Topic Candidate ────────────────────────────────────────────────
    separator("STEP 1: Topic Candidate")
    candidate = make_topic_candidate()
    print(f"  Topic   : {candidate.topic}")
    print(f"  Source  : {candidate.source}")
    print(f"  Freshness: {candidate.freshness}")
    print(f"  Evidence : {len(candidate.available_evidence)} items")

    # ── Step 2: Opportunity Scoring ────────────────────────────────────────────
    separator("STEP 2: Opportunity Scoring")
    engine = OpportunityEngine()
    engine.score(candidate)
    print(f"  Opportunity Score : {candidate.opportunity_score:.3f}")
    print(f"  Confidence        : {candidate.confidence:.3f}")
    print(f"  Recommended Formats: {candidate.recommended_formats}")
    worth_it = engine.is_worth_proceeding(candidate)
    print(f"  Worth Proceeding  : {worth_it}")
    if not worth_it:
        print("  Score below threshold — stopping.")
        return

    # ── Step 3: Topic Approval Gate ────────────────────────────────────────────
    separator("STEP 3: Topic Approval Gate")
    topic_gate = ApprovalGate(WorkflowState.TOPIC_APPROVAL)
    approved = topic_gate.request_approval(
        subject=candidate.topic,
        context=f"Score={candidate.opportunity_score}, Formats={candidate.recommended_formats}",
        human_callback=demo_approval_gate,
    )
    if not approved:
        print("  Topic rejected — stopping.")
        return
    candidate.approved = True
    print(f"  Topic approved: {candidate.topic}")

    # ── Step 4: Master Research ────────────────────────────────────────────────
    separator("STEP 4: Master Research (mock)")
    research = make_master_research(candidate.topic)
    print(f"  Topic   : {research.topic}")
    print(f"  Summary : {research.summary[:80]}...")
    print(f"  Key Facts: {len(research.key_facts)}")
    print(f"  Sources  : {len(research.sources)}")

    # ── Step 5: Content Planning ───────────────────────────────────────────────
    separator("STEP 5: Content Planning")
    planner = ContentPlanner()

    plans = []
    for fmt in ["SHORT", "UTILITY_LONG_FORM"]:
        plan = planner.plan(candidate, research, fmt)
        plans.append(plan)
        print(f"\n  [{fmt}]")
        print(f"    Hook    : {plan.hook}")
        print(f"    Sections: {len(plan.sections)}")
        print(f"    Duration: {plan.target_duration_seconds}s")
        print(f"    Budget  : {plan.budget_estimate_key}")

    # ── Step 6: Script Approval Gate (for first plan) ─────────────────────────
    separator("STEP 6: Script Approval Gate")
    script_gate = ApprovalGate(WorkflowState.SCRIPT_APPROVAL)
    approved = script_gate.request_approval(
        subject=f"Script plan: {plans[0].topic} [{plans[0].format}]",
        context=f"Hook: {plans[0].hook}",
        human_callback=demo_approval_gate,
    )
    if approved:
        plans[0].script_approval = ApprovalStatus.APPROVED
        print(f"  Script approved for {plans[0].format}")

    # ── Step 7: Retention Planning ─────────────────────────────────────────────
    separator("STEP 7: Retention Planning")
    builder = RetentionBuilder()
    retention_plans = []
    for plan in plans:
        rp = builder.build(plan)
        retention_plans.append(rp)
        errors = rp.validate()
        print(f"\n  [{plan.format}]  id={rp.id}")
        print(f"    Segments       : {len(rp.segments)}")
        print(f"    Premium seconds: {rp.premium_seconds():.1f}s")
        print(f"    Free seconds   : {rp.free_seconds():.1f}s")
        print(f"    Validation     : {'OK' if not errors else errors}")

    # ── Step 8: Production Budget ──────────────────────────────────────────────
    separator("STEP 8: Production Budget Estimate")
    cost_ctrl = CostController()
    for plan, rp in zip(plans, retention_plans):
        budget = cost_ctrl.estimate(rp, plan.budget_estimate_key)
        s = budget.summary()
        print(f"\n  [{plan.format}]")
        print(f"    Estimated cost : ${s['estimated_cost_usd']:.4f}")
        print(f"    Budget limit   : ${s['budget_limit_usd']:.2f}")
        print(f"    Within budget  : {s['within_budget']}")
        print(f"    Free assets    : {s['free_assets']}")
        print(f"    Paid assets    : {s['paid_assets']}")

    # ── Step 9: Production Approval Gate ──────────────────────────────────────
    separator("STEP 9: Production Approval Gate")
    prod_gate = ApprovalGate(WorkflowState.PRODUCTION_APPROVAL)
    prod_gate.request_approval(
        subject=f"Approve production: {plans[0].topic}",
        context="All plans and budgets reviewed",
        human_callback=demo_approval_gate,
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    separator("DEMO COMPLETE")
    print("\n  Pipeline completed successfully.")
    print(f"  Topic    : {candidate.topic}")
    print(f"  Plans    : {len(plans)}")
    print(f"  Formats  : {[p.format for p in plans]}")
    print("\n  All approval gates: PASSED (demo mode)")
    print("  Paid API usage    : NONE")
    print("  Network calls     : NONE\n")


if __name__ == "__main__":
    main()
