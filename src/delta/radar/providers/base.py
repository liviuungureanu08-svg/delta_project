"""Abstract radar source provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class SourceEvidence:
    """Raw evidence item returned by a source provider."""
    topic_hint: str                    # topic or keyword this relates to
    source_type: str                   # "youtube" | "trends" | "news" | "cross_niche"
    source_id: str                     # URL, video ID, article ID
    observed_at: datetime
    evidence_type: str                 # "breakout_video" | "search_surge" | "news_cluster" | etc.
    payload: dict[str, Any]           # provider-specific structured data
    base_confidence: float = 0.7      # source type reliability
    is_independent: bool = True       # vs. derived/duplicate signal


class RadarSourceProvider(ABC):
    """Abstract interface for all radar evidence sources."""

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Identifier for this source type."""
        ...

    @abstractmethod
    def fetch_evidence(self, topics: list[str]) -> list[SourceEvidence]:
        """Fetch evidence for the given topic hints.

        Must not make real network calls; mock implementations use fixtures.
        Returns empty list if no evidence found — never raises on missing data.
        """
        ...

    @property
    def requires_credentials(self) -> bool:
        return False
