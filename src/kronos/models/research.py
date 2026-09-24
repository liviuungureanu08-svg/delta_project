"""MasterResearch model — one research object serves multiple content formats."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ResearchSource:
    title: str
    url: Optional[str] = None
    type: str = "unknown"        # "article" | "paper" | "video" | "tool" | "unknown"
    notes: Optional[str] = None
    retrieved_at: Optional[datetime] = None


@dataclass
class MasterResearch:
    topic: str
    summary: str
    created_at: datetime = field(default_factory=datetime.utcnow)

    key_facts: list[str] = field(default_factory=list)
    key_arguments: list[str] = field(default_factory=list)
    counterarguments: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    quotes: list[str] = field(default_factory=list)
    sources: list[ResearchSource] = field(default_factory=list)

    # Structured angles per format — optional pre-extracted angles
    short_angles: list[str] = field(default_factory=list)
    long_form_angles: list[str] = field(default_factory=list)
    documentary_angles: list[str] = field(default_factory=list)
    instagram_angles: list[str] = field(default_factory=list)

    notes: Optional[str] = None
