"""Search interest provider interface.

Phase 3 status: DISABLED / UNAVAILABLE.

No official, stable, free Google Trends API is available that meets these
constraints (no scraping, no paid services, no fragile unofficial wrappers).

Preserved as an integration point. Enable when an appropriate official
source becomes available. Delta runs correctly without this provider.

NOT implemented / NOT enabled in Phase 3:
  - PyTrends (unofficial scraping of trends.google.com — fragile, brittle)
  - SerpAPI (paid service — not automatically enabled)
  - Google Ads Keyword Planner (requires active Ads account)
  - Google Search Console (requires site ownership)
"""

from __future__ import annotations

import logging

from delta.radar.providers.base import RadarSourceProvider, SourceEvidence

logger = logging.getLogger(__name__)


class SearchInterestProvider(RadarSourceProvider):
    """Interface for search-interest / trends data.

    Always returns empty evidence in the current phase.
    Set enabled=True only when a verified official integration is wired in.
    """

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled

    @property
    def source_type(self) -> str:
        return "search_interest"

    @property
    def requires_credentials(self) -> bool:
        return True

    @property
    def is_available(self) -> bool:
        return self._enabled

    def fetch_evidence(self, topics: list[str]) -> list[SourceEvidence]:
        if not self._enabled:
            logger.debug(
                "SearchInterestProvider disabled — returning no evidence. "
                "Radar continues without search-interest signals."
            )
            return []
        return []
