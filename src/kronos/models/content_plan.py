"""ContentPlan and related models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


@dataclass
class ContentSection:
    title: str
    purpose: str                  # role in the video (hook/body/proof/cta/etc.)
    duration_seconds: Optional[int] = None
    key_points: list[str] = field(default_factory=list)
    research_ref_keys: list[str] = field(default_factory=list)


@dataclass
class ContentPlan:
    format: str                   # matches a key in channel.yaml formats
    topic: str
    objective: str
    target_audience: str
    core_angle: str
    hook: str

    sections: list[ContentSection] = field(default_factory=list)
    target_duration_seconds: Optional[int] = None

    cta_concept: Optional[str] = None
    production_requirements: list[str] = field(default_factory=list)

    # References
    research_topic: Optional[str] = None     # links to MasterResearch.topic
    retention_plan_id: Optional[str] = None  # links to RetentionPlan.id
    budget_estimate_key: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.utcnow)
    script_approval: ApprovalStatus = ApprovalStatus.PENDING
    production_approval: ApprovalStatus = ApprovalStatus.PENDING
    publish_approval: ApprovalStatus = ApprovalStatus.PENDING

    def total_duration(self) -> int:
        return sum(s.duration_seconds or 0 for s in self.sections)
