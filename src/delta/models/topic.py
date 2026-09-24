"""TopicCandidate model — represents a content opportunity to evaluate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class DemandIndicators:
    search_trend: Optional[str] = None        # "rising" | "stable" | "falling" | None
    social_buzz: Optional[str] = None         # qualitative signal only
    news_coverage: Optional[str] = None       # qualitative
    # Real search volumes / metrics are intentionally absent until live research integrations exist


@dataclass
class CompetitionIndicators:
    saturation: Optional[str] = None          # "low" | "medium" | "high" | None
    dominant_players: list[str] = field(default_factory=list)
    gap_observed: Optional[str] = None        # qualitative description of an unmet angle


@dataclass
class TopicCandidate:
    topic: str
    source: str                               # where the idea came from
    discovered_at: datetime = field(default_factory=datetime.utcnow)

    why_now: Optional[str] = None
    audience_relevance: Optional[str] = None  # qualitative
    demand: DemandIndicators = field(default_factory=DemandIndicators)
    competition: CompetitionIndicators = field(default_factory=CompetitionIndicators)
    freshness: Optional[str] = None           # "very fresh" | "fresh" | "evergreen" | "dated"
    monetization_potential: Optional[str] = None  # qualitative; real RPM not known
    title_potential: Optional[str] = None
    thumbnail_potential: Optional[str] = None
    available_evidence: list[str] = field(default_factory=list)

    # Scored fields — populated by OpportunityEngine
    confidence: float = 0.0                   # 0.0–1.0; set by scorer
    opportunity_score: float = 0.0            # 0.0–1.0; set by scorer
    recommended_formats: list[str] = field(default_factory=list)

    # Approval
    approved: Optional[bool] = None           # None = pending decision

    def is_approved(self) -> bool:
        return self.approved is True
