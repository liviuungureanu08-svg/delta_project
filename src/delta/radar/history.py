"""Lightweight local observation history for trend comparison."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Observation:
    """A single timestamped observation for change-over-time tracking."""

    observation_id: str         # unique key: e.g. "yt:VIDEO_ID:2024-01-01"
    source_type: str            # "youtube" | "news" | "trends"
    topic_hint: str
    item_id: str                # video_id, article_id, etc.
    channel_id: Optional[str]
    observed_at: str            # ISO8601 string
    observed_views: Optional[int]
    channel_baseline: Optional[int]
    relative_performance: Optional[float]
    extra: dict = field(default_factory=dict)


class ObservationHistory:
    """JSON-file-backed observation store.

    Stores only what is needed for trend comparison:
    - source item identity
    - timestamp
    - observed views + channel baseline
    - relative performance

    Does NOT store full article bodies or video transcripts.
    """

    def __init__(self, data_dir: str = "data/observations") -> None:
        self._path = Path(data_dir) / "observations.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if self._path.exists():
            try:
                with open(self._path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def save(self) -> None:
        with open(self._path, "w") as f:
            json.dump(self._records, f, indent=2, default=str)

    def record(self, obs: Observation) -> bool:
        """Store observation. Returns True if new (not previously seen)."""
        is_new = obs.observation_id not in self._records
        self._records[obs.observation_id] = asdict(obs)
        return is_new

    def get(self, observation_id: str) -> Optional[dict]:
        return self._records.get(observation_id)

    def get_by_item(self, item_id: str) -> list[dict]:
        return [r for r in self._records.values() if r.get("item_id") == item_id]

    def get_by_topic(self, topic_hint: str) -> list[dict]:
        th = topic_hint.lower()
        return [
            r for r in self._records.values()
            if th in r.get("topic_hint", "").lower()
        ]

    def get_by_channel(self, channel_id: str) -> list[dict]:
        return [r for r in self._records.values() if r.get("channel_id") == channel_id]

    def get_all(self) -> list[dict]:
        return list(self._records.values())

    def count(self) -> int:
        return len(self._records)
