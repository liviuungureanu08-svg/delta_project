"""Request quota / budget tracking for live providers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProviderQuota:
    """Tracks API request budget for a single provider.

    Priority ordering for scarce quota (enforced by callers):
      1. WATCH candidates
      2. high-potential existing candidates
      3. primary AI/Tech discovery
      4. cross-niche exploration
    """

    provider_name: str
    daily_budget: int
    requests_made: int = 0
    cache_hits: int = 0
    failed_requests: int = 0
    available: bool = True

    @property
    def remaining(self) -> int:
        return max(0, self.daily_budget - self.requests_made)

    @property
    def is_exhausted(self) -> bool:
        return self.requests_made >= self.daily_budget

    def consume(self, count: int = 1) -> bool:
        """Consume count request units. Returns True if budget was available."""
        if self.requests_made + count > self.daily_budget:
            return False
        self.requests_made += count
        return True

    def record_cache_hit(self) -> None:
        self.cache_hits += 1

    def record_failure(self) -> None:
        self.failed_requests += 1

    def to_dict(self) -> dict:
        return {
            "provider": self.provider_name,
            "daily_budget": self.daily_budget,
            "requests_made": self.requests_made,
            "remaining": self.remaining,
            "cache_hits": self.cache_hits,
            "failed_requests": self.failed_requests,
            "available": self.available,
            "exhausted": self.is_exhausted,
        }
