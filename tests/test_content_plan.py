"""Tests for ContentPlanner."""

import pytest
from delta.config import reload_all
from delta.engine import ContentPlanner
from delta.models.content_plan import ApprovalStatus
from delta.models.research import MasterResearch
from delta.models.topic import TopicCandidate


@pytest.fixture(autouse=True)
def clear_cache():
    reload_all()
    yield
    reload_all()


@pytest.fixture
def approved_candidate():
    c = TopicCandidate(
        topic="Test AI Topic",
        source="test",
        approved=True,
        why_now="Something important just happened",
    )
    return c


@pytest.fixture
def research():
    return MasterResearch(
        topic="Test AI Topic",
        summary="A summary of the topic.",
        key_facts=["Fact 1", "Fact 2", "Fact 3", "Fact 4"],
        key_arguments=["Argument 1", "Argument 2"],
    )


def test_plan_short(approved_candidate, research):
    planner = ContentPlanner()
    plan = planner.plan(approved_candidate, research, "SHORT")
    assert plan.format == "SHORT"
    assert plan.topic == "Test AI Topic"
    assert len(plan.sections) >= 2
    assert plan.target_duration_seconds is not None
    assert plan.script_approval == ApprovalStatus.PENDING


def test_plan_long_form(approved_candidate, research):
    planner = ContentPlanner()
    plan = planner.plan(approved_candidate, research, "UTILITY_LONG_FORM")
    assert plan.format == "UTILITY_LONG_FORM"
    assert len(plan.sections) >= 3
    assert plan.target_duration_seconds > 60


def test_plan_instagram_post(approved_candidate, research):
    planner = ContentPlanner()
    plan = planner.plan(approved_candidate, research, "INSTAGRAM_POST")
    assert plan.format == "INSTAGRAM_POST"
    assert len(plan.sections) >= 1


def test_plan_instagram_carousel(approved_candidate, research):
    planner = ContentPlanner()
    plan = planner.plan(approved_candidate, research, "INSTAGRAM_CAROUSEL")
    assert plan.format == "INSTAGRAM_CAROUSEL"
    assert len(plan.sections) >= 3


def test_unapproved_raises(research):
    planner = ContentPlanner()
    c = TopicCandidate(topic="Test", source="test", approved=False)
    with pytest.raises(ValueError, match="unapproved"):
        planner.plan(c, research, "SHORT")


def test_unknown_format_raises(approved_candidate, research):
    planner = ContentPlanner()
    with pytest.raises(ValueError, match="Unknown format"):
        planner.plan(approved_candidate, research, "NONEXISTENT_FORMAT")


def test_total_duration_short(approved_candidate, research):
    planner = ContentPlanner()
    plan = planner.plan(approved_candidate, research, "SHORT")
    total = plan.total_duration()
    assert total <= 60, f"SHORT total duration {total}s exceeds 60s"
