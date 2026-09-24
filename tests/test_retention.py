"""Tests for RetentionBuilder and RetentionPlan."""

import pytest
from kronos.config import reload_all
from kronos.engine import RetentionBuilder
from kronos.models.content_plan import ContentPlan, ContentSection
from kronos.models.retention import AssetType, RetentionPlan, TimelineSegment


@pytest.fixture(autouse=True)
def clear_cache():
    reload_all()
    yield
    reload_all()


def _make_plan(format: str, duration: int) -> ContentPlan:
    return ContentPlan(
        format=format,
        topic="Test Topic",
        objective="obj",
        target_audience="audience",
        core_angle="angle",
        hook="hook",
        target_duration_seconds=duration,
    )


def test_retention_plan_has_segments():
    builder = RetentionBuilder()
    plan = _make_plan("SHORT", 45)
    rp = builder.build(plan)
    assert len(rp.segments) > 0


def test_retention_covers_full_duration():
    builder = RetentionBuilder()
    plan = _make_plan("SHORT", 45)
    rp = builder.build(plan)
    last_end = rp.segments[-1].end_second
    assert abs(last_end - 45.0) < 0.01


def test_retention_segments_are_contiguous():
    builder = RetentionBuilder()
    plan = _make_plan("UTILITY_LONG_FORM", 600)
    rp = builder.build(plan)
    for i in range(1, len(rp.segments)):
        assert rp.segments[i].start_second == rp.segments[i - 1].end_second


def test_retention_validate_clean():
    builder = RetentionBuilder()
    plan = _make_plan("SHORT", 30)
    rp = builder.build(plan)
    errors = rp.validate()
    assert errors == []


def test_retention_validate_catches_bad_segment():
    rp = RetentionPlan()
    rp.segments.append(TimelineSegment(
        start_second=10.0,
        end_second=5.0,   # invalid: end < start
        asset_type=AssetType.SCREENSHOT,
        description="bad",
    ))
    errors = rp.validate()
    assert len(errors) == 1


def test_retention_premium_seconds_for_short():
    builder = RetentionBuilder()
    plan = _make_plan("SHORT", 45)
    rp = builder.build(plan)
    # AI_GENERATED_VIDEO is the only premium type
    ai_secs = sum(s.duration for s in rp.segments if s.asset_type == AssetType.AI_GENERATED_VIDEO)
    assert rp.premium_seconds() == ai_secs


def test_retention_free_plus_premium_equals_total():
    builder = RetentionBuilder()
    plan = _make_plan("UTILITY_LONG_FORM", 300)
    rp = builder.build(plan)
    assert abs(rp.free_seconds() + rp.premium_seconds() - rp.total_duration_seconds) < 0.01
