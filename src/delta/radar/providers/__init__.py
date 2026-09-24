"""Radar source providers — abstract interfaces, mock and live implementations."""

from .base import RadarSourceProvider, SourceEvidence
from .live_news import LiveNewsProvider
from .live_youtube import LiveYouTubeProvider
from .news import MockNewsProvider
from .search_interest import SearchInterestProvider
from .trends import MockTrendsProvider
from .youtube import MockYouTubeProvider

__all__ = [
    "RadarSourceProvider",
    "SourceEvidence",
    # Mock (offline / test)
    "MockYouTubeProvider",
    "MockTrendsProvider",
    "MockNewsProvider",
    # Live (require environment / network)
    "LiveYouTubeProvider",
    "LiveNewsProvider",
    "SearchInterestProvider",
]
