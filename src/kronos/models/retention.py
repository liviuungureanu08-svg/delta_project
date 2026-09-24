"""RetentionPlan — timeline-based visual pacing model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


class AssetType(Enum):
    AI_GENERATED_VIDEO = "AI_GENERATED_VIDEO"
    SCREENSHOT = "SCREENSHOT"
    SCREEN_RECORDING = "SCREEN_RECORDING"
    STATIC_IMAGE = "STATIC_IMAGE"
    GENERATED_IMAGE = "GENERATED_IMAGE"
    TEXT_OVERLAY = "TEXT_OVERLAY"
    GRAPHIC = "GRAPHIC"
    CHART = "CHART"
    B_ROLL = "B_ROLL"
    ZOOM_PAN = "ZOOM_PAN"
    TRANSITION = "TRANSITION"


@dataclass
class TimelineSegment:
    start_second: float
    end_second: float
    asset_type: AssetType
    description: str
    is_premium: bool = False      # True = AI-generated / paid
    notes: Optional[str] = None

    @property
    def duration(self) -> float:
        return self.end_second - self.start_second


@dataclass
class RetentionPlan:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    content_plan_topic: str = ""
    format: str = ""
    total_duration_seconds: float = 0.0
    segments: list[TimelineSegment] = field(default_factory=list)

    def premium_seconds(self) -> float:
        return sum(s.duration for s in self.segments if s.is_premium)

    def free_seconds(self) -> float:
        return sum(s.duration for s in self.segments if not s.is_premium)

    def validate(self) -> list[str]:
        """Return list of validation errors (empty = valid)."""
        errors = []
        for i, seg in enumerate(self.segments):
            if seg.start_second < 0:
                errors.append(f"Segment {i}: negative start_second")
            if seg.end_second <= seg.start_second:
                errors.append(f"Segment {i}: end_second must be > start_second")
        return errors
