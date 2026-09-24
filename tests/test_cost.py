"""Tests for CostController and ProductionBudget."""

import pytest
from kronos.config import reload_all
from kronos.engine import CostController, RetentionBuilder
from kronos.models.content_plan import ContentPlan
from kronos.models.retention import AssetType, RetentionPlan, TimelineSegment


@pytest.fixture(autouse=True)
def clear_cache():
    reload_all()
    yield
    reload_all()


def _make_retention_plan(format: str, segments: list) -> RetentionPlan:
    rp = RetentionPlan(content_plan_topic="Test", format=format)
    rp.segments = segments
    if segments:
        rp.total_duration_seconds = segments[-1].end_second
    return rp


def test_mock_provider_costs_zero():
    ctrl = CostController()
    rp = _make_retention_plan("SHORT", [
        TimelineSegment(0, 5, AssetType.AI_GENERATED_VIDEO, "ai", is_premium=True),
        TimelineSegment(5, 10, AssetType.SCREENSHOT, "ss"),
    ])
    budget = ctrl.estimate(rp, "short")
    assert budget.estimated_total_usd() == 0.0


def test_within_budget_for_mock():
    ctrl = CostController()
    rp = _make_retention_plan("SHORT", [
        TimelineSegment(0, 10, AssetType.AI_GENERATED_VIDEO, "ai", is_premium=True),
    ])
    budget = ctrl.estimate(rp, "short")
    assert budget.within_budget()


def test_budget_key_sets_limit():
    ctrl = CostController()
    rp = _make_retention_plan("UTILITY_LONG_FORM", [
        TimelineSegment(0, 60, AssetType.SCREEN_RECORDING, "sr"),
    ])
    budget = ctrl.estimate(rp, "long_form")
    assert budget.budget_limit_usd is not None
    assert budget.budget_limit_usd > 0


def test_unknown_budget_key_raises():
    ctrl = CostController()
    rp = _make_retention_plan("SHORT", [])
    with pytest.raises(ValueError, match="Unknown budget key"):
        ctrl.estimate(rp, "nonexistent_key")


def test_free_asset_counted():
    ctrl = CostController()
    rp = _make_retention_plan("SHORT", [
        TimelineSegment(0, 5, AssetType.SCREENSHOT, "ss"),
        TimelineSegment(5, 10, AssetType.TEXT_OVERLAY, "to"),
        TimelineSegment(10, 15, AssetType.GRAPHIC, "gr"),
    ])
    budget = ctrl.estimate(rp, "short")
    assert budget.free_asset_count >= 3


def test_summary_structure():
    ctrl = CostController()
    rp = _make_retention_plan("SHORT", [
        TimelineSegment(0, 5, AssetType.SCREENSHOT, "ss"),
    ])
    budget = ctrl.estimate(rp, "short")
    s = budget.summary()
    for key in ["format", "estimated_cost_usd", "budget_limit_usd", "within_budget"]:
        assert key in s, f"Missing key in summary: {key}"
