"""Tests for ProviderQuota budget tracking."""

import pytest
from delta.radar.quota import ProviderQuota


def make_quota(budget: int = 10) -> ProviderQuota:
    return ProviderQuota(provider_name="test", daily_budget=budget)


def test_initial_state():
    q = make_quota(10)
    assert q.requests_made == 0
    assert q.remaining == 10
    assert not q.is_exhausted
    assert q.available


def test_consume_decrements_remaining():
    q = make_quota(10)
    assert q.consume(3)
    assert q.requests_made == 3
    assert q.remaining == 7


def test_consume_returns_false_when_over_budget():
    q = make_quota(5)
    assert q.consume(5)
    assert not q.consume(1)
    assert q.requests_made == 5


def test_consume_exact_budget():
    q = make_quota(3)
    assert q.consume(3)
    assert q.is_exhausted
    assert q.remaining == 0


def test_exhausted_after_all_units_consumed():
    q = make_quota(2)
    q.consume(1)
    q.consume(1)
    assert q.is_exhausted


def test_cache_hit_tracking():
    q = make_quota(10)
    q.record_cache_hit()
    q.record_cache_hit()
    assert q.cache_hits == 2
    assert q.requests_made == 0


def test_failure_tracking():
    q = make_quota(10)
    q.record_failure()
    assert q.failed_requests == 1


def test_to_dict_contains_required_keys():
    q = make_quota(100)
    q.consume(10)
    q.record_cache_hit()
    q.record_failure()
    d = q.to_dict()
    assert d["daily_budget"] == 100
    assert d["requests_made"] == 10
    assert d["remaining"] == 90
    assert d["cache_hits"] == 1
    assert d["failed_requests"] == 1
    assert not d["exhausted"]
    assert d["available"]


def test_available_flag_respected():
    q = make_quota(10)
    q.available = False
    assert not q.available
    # is_exhausted is independent of available flag
    assert not q.is_exhausted
