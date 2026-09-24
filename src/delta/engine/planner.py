"""ContentPlanner — transforms approved TopicCandidate + MasterResearch into ContentPlans."""

from __future__ import annotations

from delta.config import channel_config
from delta.models.content_plan import ContentPlan, ContentSection, ApprovalStatus
from delta.models.research import MasterResearch
from delta.models.topic import TopicCandidate


class ContentPlanner:
    def __init__(self) -> None:
        self._channel = channel_config()

    def plan(
        self,
        candidate: TopicCandidate,
        research: MasterResearch,
        format: str,
    ) -> ContentPlan:
        if not candidate.is_approved():
            raise ValueError("Cannot plan content for an unapproved topic")

        fmt_cfg = self._channel["formats"].get(format)
        if fmt_cfg is None:
            raise ValueError(f"Unknown format: {format}")

        duration_range = fmt_cfg.get("target_duration_seconds")
        target_duration = int(sum(duration_range) / 2) if duration_range else None

        sections = self._build_sections(format, research, target_duration)

        return ContentPlan(
            format=format,
            topic=candidate.topic,
            objective=f"Educate and engage the audience on: {candidate.topic}",
            target_audience=self._channel["channel"]["target_audience"],
            core_angle=candidate.why_now or f"What you need to know about {candidate.topic}",
            hook=self._build_hook(candidate, format),
            sections=sections,
            target_duration_seconds=target_duration,
            cta_concept="Subscribe for more AI & Tech content",
            production_requirements=self._production_requirements(format),
            research_topic=research.topic,
            budget_estimate_key=fmt_cfg.get("production_budget_key"),
        )

    def _build_hook(self, candidate: TopicCandidate, format: str) -> str:
        if candidate.why_now:
            return f"[HOOK] {candidate.why_now}"
        return f"[HOOK] Here's what's changing right now with {candidate.topic}"

    def _build_sections(
        self, format: str, research: MasterResearch, total_seconds: int | None
    ) -> list[ContentSection]:
        if format == "SHORT":
            return self._sections_short(research, total_seconds or 45)
        elif format in ("UTILITY_LONG_FORM", "DOCUMENTARY"):
            return self._sections_long(research, total_seconds or 600, format)
        elif format in ("INSTAGRAM_POST", "INSTAGRAM_CAROUSEL"):
            return self._sections_instagram(research, format)
        return []

    def _sections_short(self, research: MasterResearch, total: int) -> list[ContentSection]:
        hook_t = min(5, int(total * 0.12))
        main_t = total - hook_t - 5
        return [
            ContentSection("Hook", "hook", hook_t, research.key_facts[:1]),
            ContentSection("Core Point", "body", main_t, research.key_facts[1:3]),
            ContentSection("CTA", "cta", 5, []),
        ]

    def _sections_long(self, research: MasterResearch, total: int, format: str) -> list[ContentSection]:
        hook_t = 60
        intro_t = 90
        sections_count = 4
        body_t = (total - hook_t - intro_t - 60 - 60) // sections_count
        return [
            ContentSection("Hook", "hook", hook_t, research.key_facts[:1]),
            ContentSection("Introduction", "intro", intro_t, research.key_arguments[:1]),
            *[
                ContentSection(
                    f"Section {i+1}",
                    "body",
                    body_t,
                    research.key_facts[i : i + 2],
                )
                for i in range(sections_count)
            ],
            ContentSection("Conclusion", "conclusion", 60, research.key_arguments[-1:]),
            ContentSection("CTA", "cta", 60, []),
        ]

    def _sections_instagram(self, research: MasterResearch, format: str) -> list[ContentSection]:
        if format == "INSTAGRAM_POST":
            return [
                ContentSection("Visual Hook", "hook", None, research.key_facts[:1]),
                ContentSection("Caption Body", "body", None, research.key_facts[1:3]),
            ]
        return [
            ContentSection(f"Slide {i+1}", "body", None, research.key_facts[i : i + 1])
            for i in range(min(6, max(3, len(research.key_facts))))
        ]

    def _production_requirements(self, format: str) -> list[str]:
        base = ["Voiceover script", "Background music"]
        if format == "SHORT":
            return base + ["Vertical 9:16 format", "Captions/subtitles"]
        if format == "UTILITY_LONG_FORM":
            return base + ["Intro/outro graphics", "Chapter markers", "Thumbnail"]
        if format == "DOCUMENTARY":
            return base + ["Extended research sources", "Narrator voice", "Documentary-style B-roll"]
        if format == "INSTAGRAM_POST":
            return ["Single high-quality visual", "Caption copy"]
        if format == "INSTAGRAM_CAROUSEL":
            return ["Carousel slides (3–10)", "Cover slide", "Caption copy"]
        return base
