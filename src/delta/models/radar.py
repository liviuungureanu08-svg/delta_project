"""Phase 2 radar models — evidence, signals, candidate lifecycle, opportunity reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class LifecycleState(Enum):
    DISCOVERED = "DISCOVERED"
    WATCH = "WATCH"
    VALIDATED = "VALIDATED"
    TOP_5 = "TOP_5"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    REJECTED = "REJECTED"


class SaturationState(Enum):
    EARLY = "EARLY"
    EMERGING = "EMERGING"
    ACCELERATING = "ACCELERATING"
    MAINSTREAM = "MAINSTREAM"
    SATURATED = "SATURATED"


class MomentumState(Enum):
    ACCELERATING = "ACCELERATING"
    RISING = "RISING"
    STABLE = "STABLE"
    DECLINING = "DECLINING"
    UNKNOWN = "UNKNOWN"


@dataclass
class Evidence:
    """A single piece of evidence from a source, with full provenance."""
    source_type: str          # "youtube" | "trends" | "news" | "cross_niche" | "mock"
    source_id: str            # URL, channel ID, or identifier
    observed_at: datetime
    evidence_type: str        # "view_velocity" | "search_trend" | "news_mention" | "breakout" | etc.
    observed_value: Any       # raw observed value (number, string, dict)
    confidence: float         # 0.0–1.0 source reliability
    is_independent: bool      # False if derived or duplicate of another source
    notes: Optional[str] = None


@dataclass
class YouTubeVideoEvidence:
    """Structured evidence for a YouTube video signal."""
    video_id: str
    channel_id: str
    title: str
    topic_tags: list[str]
    published_at: datetime
    views_at_observation: int
    observation_age_hours: float    # hours since publication
    channel_baseline_views: int     # channel's normal per-video baseline
    channel_upload_frequency_days: float

    @property
    def relative_performance(self) -> float:
        """View count relative to channel baseline. >1.0 means outperforming."""
        if self.channel_baseline_views <= 0:
            return 0.0
        return self.views_at_observation / self.channel_baseline_views

    @property
    def view_velocity(self) -> float:
        """Views per hour since publication."""
        if self.observation_age_hours <= 0:
            return 0.0
        return self.views_at_observation / self.observation_age_hours

    def is_breakout(self, multiplier_threshold: float = 3.0) -> bool:
        return self.relative_performance >= multiplier_threshold


@dataclass
class Signals:
    """Normalized signal set derived from collected evidence."""
    momentum: MomentumState = MomentumState.UNKNOWN
    freshness_days: Optional[int] = None         # days since first observed
    independent_source_count: int = 0            # deduplicated independent sources
    cross_source_confirmed: bool = False          # confirmed by 2+ independent sources
    youtube_breakout: bool = False               # breakout relative to channel baseline
    channel_relative_multiplier: Optional[float] = None   # best observed multiplier
    topic_recurrence_count: int = 0              # number of independent channels covering it
    saturation_state: SaturationState = SaturationState.EARLY
    production_feasibility: str = "unknown"      # "high" | "medium" | "low" | "unknown"
    monetization_strength: str = "unknown"       # "high" | "medium" | "low" | "unknown"
    title_potential: str = "unknown"
    thumbnail_potential: str = "unknown"
    audience_relevance: str = "unknown"


@dataclass
class RadarCandidate:
    """Extended candidate with full radar evidence, signals, and lifecycle state."""
    topic: str
    niche: str                               # "ai_tech" | "cross_niche"
    lifecycle: LifecycleState = LifecycleState.DISCOVERED
    discovered_at: datetime = field(default_factory=datetime.utcnow)

    evidence: list[Evidence] = field(default_factory=list)
    signals: Signals = field(default_factory=Signals)

    opportunity_score: float = 0.0           # 0.0–1.0; what the opportunity looks like
    confidence_score: float = 0.0           # 0.0–1.0; how much we trust the evidence
    saturation_state: SaturationState = SaturationState.EARLY
    momentum_state: MomentumState = MomentumState.UNKNOWN

    why_now: Optional[str] = None
    strongest_evidence_summary: Optional[str] = None
    main_risk: Optional[str] = None
    score_explanation: list[str] = field(default_factory=list)

    human_approved: Optional[bool] = None    # None = pending

    def independent_evidence_count(self) -> int:
        return sum(1 for e in self.evidence if e.is_independent)

    def has_independent_confirmation(self, minimum: int = 2) -> bool:
        return self.independent_evidence_count() >= minimum


@dataclass
class OpportunityReport:
    """Compact recommendation for a single validated opportunity."""
    topic: str
    niche: str
    lifecycle: LifecycleState
    opportunity_score: float
    confidence_score: float
    momentum_state: MomentumState
    saturation_state: SaturationState
    why_now: str
    strongest_evidence: str
    main_risk: str
    recommended_formats: list[str]
    suggested_angle: str
    human_approved: Optional[bool] = None   # None = awaiting approval

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "niche": self.niche,
            "lifecycle": self.lifecycle.value,
            "opportunity_score": round(self.opportunity_score, 3),
            "confidence_score": round(self.confidence_score, 3),
            "momentum": self.momentum_state.value,
            "saturation": self.saturation_state.value,
            "why_now": self.why_now,
            "strongest_evidence": self.strongest_evidence,
            "main_risk": self.main_risk,
            "recommended_formats": self.recommended_formats,
            "suggested_angle": self.suggested_angle,
            "human_approved": self.human_approved,
        }


@dataclass
class DailyTop5:
    """The daily output: maximum 5 opportunity reports awaiting human approval."""
    generated_at: datetime = field(default_factory=datetime.utcnow)
    reports: list[OpportunityReport] = field(default_factory=list)
    candidates_evaluated: int = 0
    candidates_rejected: int = 0

    def __post_init__(self) -> None:
        if len(self.reports) > 5:
            raise ValueError("DailyTop5 cannot contain more than 5 reports")

    def all_pending_approval(self) -> bool:
        return all(r.human_approved is None for r in self.reports)
