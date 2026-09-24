"""Tests for configuration loading."""

import pytest
from kronos.config import (
    budgets_config,
    channel_config,
    providers_config,
    reload_all,
    retention_config,
    scoring_config,
)


@pytest.fixture(autouse=True)
def clear_cache():
    reload_all()
    yield
    reload_all()


def test_channel_config_loads():
    cfg = channel_config()
    assert "channel" in cfg
    assert cfg["channel"]["niche"] == "AI / Technology"


def test_channel_formats_present():
    cfg = channel_config()
    for fmt in ["SHORT", "UTILITY_LONG_FORM", "DOCUMENTARY", "INSTAGRAM_POST", "INSTAGRAM_CAROUSEL"]:
        assert fmt in cfg["formats"], f"Missing format: {fmt}"


def test_approval_defaults_to_human():
    cfg = channel_config()
    approval = cfg.get("approval", {})
    for gate in ["topic_approval", "script_approval", "production_approval", "publish_approval"]:
        assert approval.get(gate) == "human", f"Gate {gate} should default to human"


def test_budgets_config_loads():
    cfg = budgets_config()
    assert "budgets" in cfg
    per_fmt = cfg["budgets"]["per_format"]
    for key in ["short", "long_form", "documentary"]:
        assert key in per_fmt, f"Missing budget key: {key}"
        assert per_fmt[key]["max_usd"] > 0


def test_providers_config_loads():
    cfg = providers_config()
    assert cfg["providers"]["video"]["default"] == "mock"
    assert cfg["providers"]["image"]["default"] == "mock"


def test_scoring_config_loads():
    cfg = scoring_config()
    weights = cfg["scoring"]["weights"]
    total = sum(weights.values())
    assert abs(total - 1.0) < 1e-9, f"Scoring weights must sum to 1.0, got {total}"


def test_retention_config_loads():
    cfg = retention_config()
    pacing = cfg["retention"]["pacing"]
    assert pacing["hook_window_seconds"] > 0
    assert pacing["body_change_interval_seconds"] > 0
