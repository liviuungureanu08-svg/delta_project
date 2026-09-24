"""Tests for ObservationHistory local persistence."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from delta.radar.history import Observation, ObservationHistory


def make_obs(item_id: str = "vid_001", channel_id: str = "ch_a", views: int = 1000) -> Observation:
    return Observation(
        observation_id=f"yt:{item_id}:2026-01-01",
        source_type="youtube",
        topic_hint="test topic",
        item_id=item_id,
        channel_id=channel_id,
        observed_at="2026-01-01T00:00:00+00:00",
        observed_views=views,
        channel_baseline=500,
        relative_performance=views / 500,
    )


def make_history(tmp_path: Path) -> ObservationHistory:
    return ObservationHistory(data_dir=str(tmp_path / "obs"))


def test_record_new_observation_returns_true(tmp_path):
    h = make_history(tmp_path)
    obs = make_obs()
    assert h.record(obs) is True


def test_record_existing_observation_returns_false(tmp_path):
    h = make_history(tmp_path)
    obs = make_obs()
    h.record(obs)
    assert h.record(obs) is False


def test_count_after_records(tmp_path):
    h = make_history(tmp_path)
    h.record(make_obs("v1"))
    h.record(make_obs("v2"))
    assert h.count() == 2


def test_get_by_item(tmp_path):
    h = make_history(tmp_path)
    h.record(make_obs("vid_special"))
    h.record(make_obs("vid_other"))
    results = h.get_by_item("vid_special")
    assert len(results) == 1
    assert results[0]["item_id"] == "vid_special"


def test_get_by_channel(tmp_path):
    h = make_history(tmp_path)
    h.record(make_obs("v1", channel_id="ch_target"))
    h.record(make_obs("v2", channel_id="ch_other"))
    results = h.get_by_channel("ch_target")
    assert len(results) == 1
    assert results[0]["channel_id"] == "ch_target"


def test_get_by_topic(tmp_path):
    h = make_history(tmp_path)
    obs = Observation(
        observation_id="yt:v:2026-01-01",
        source_type="youtube",
        topic_hint="Claude AI coding",
        item_id="v",
        channel_id="ch",
        observed_at="2026-01-01T00:00:00+00:00",
        observed_views=100,
        channel_baseline=50,
        relative_performance=2.0,
    )
    h.record(obs)
    assert len(h.get_by_topic("claude ai")) == 1
    assert len(h.get_by_topic("unrelated")) == 0


def test_save_and_reload(tmp_path):
    h1 = make_history(tmp_path)
    h1.record(make_obs("v1", views=2000))
    h1.save()

    h2 = make_history(tmp_path)
    assert h2.count() == 1
    item = h2.get("yt:v1:2026-01-01")
    assert item is not None
    assert item["observed_views"] == 2000


def test_empty_history_returns_empty_lists(tmp_path):
    h = make_history(tmp_path)
    assert h.get_all() == []
    assert h.get_by_item("anything") == []
    assert h.get_by_channel("anything") == []


def test_corrupted_file_loads_empty(tmp_path):
    obs_dir = tmp_path / "obs"
    obs_dir.mkdir()
    (obs_dir / "observations.json").write_text("NOT JSON {{{{")
    h = ObservationHistory(data_dir=str(obs_dir))
    assert h.count() == 0


def test_observation_extra_defaults_to_empty_dict(tmp_path):
    obs = Observation(
        observation_id="yt:v:2026-01-01",
        source_type="youtube",
        topic_hint="topic",
        item_id="v",
        channel_id=None,
        observed_at="2026-01-01T00:00:00+00:00",
        observed_views=None,
        channel_baseline=None,
        relative_performance=None,
    )
    h = make_history(tmp_path)
    h.record(obs)
    stored = h.get("yt:v:2026-01-01")
    assert stored["extra"] == {}
