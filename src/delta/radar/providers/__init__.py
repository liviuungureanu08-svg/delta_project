"""Radar source providers — abstract interfaces and mock implementations."""

from .base import RadarSourceProvider, SourceEvidence
from .youtube import MockYouTubeProvider
from .trends import MockTrendsProvider
from .news import MockNewsProvider

__all__ = [
    "RadarSourceProvider", "SourceEvidence",
    "MockYouTubeProvider",
    "MockTrendsProvider",
    "MockNewsProvider",
]
