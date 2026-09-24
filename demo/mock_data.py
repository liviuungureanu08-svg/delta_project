"""Mock seed data for offline demonstration."""

from __future__ import annotations

from datetime import datetime

from delta.models.research import MasterResearch, ResearchSource
from delta.models.topic import CompetitionIndicators, DemandIndicators, TopicCandidate


def make_topic_candidate() -> TopicCandidate:
    return TopicCandidate(
        topic="Claude's new computer-use capabilities",
        source="manual_observation",
        discovered_at=datetime(2026, 9, 24),
        why_now="Anthropic just expanded computer-use to all API tiers — mainstream developers can now build AI agents that control real desktops",
        audience_relevance="high",
        demand=DemandIndicators(
            search_trend="rising",
            social_buzz="High discussion on tech forums and developer communities",
            news_coverage="Multiple major tech publications covering the release",
        ),
        competition=CompetitionIndicators(
            saturation="medium",
            dominant_players=["MajorTechChannel1", "AINewsChannel2"],
            gap_observed="Practical hands-on demonstrations and real-world use-cases are underrepresented",
        ),
        freshness="very fresh",
        monetization_potential="high",
        title_potential="excellent",
        thumbnail_potential="good",
        available_evidence=[
            "Anthropic blog post",
            "API documentation update",
            "Developer forum threads",
            "GitHub issues from early adopters",
        ],
    )


def make_master_research(topic: str) -> MasterResearch:
    return MasterResearch(
        topic=topic,
        summary=(
            "Claude's computer-use feature enables AI models to interact with computer interfaces "
            "by taking screenshots, moving the mouse, and typing. This opens a new category of "
            "AI agent applications for automation, accessibility, and developer productivity."
        ),
        key_facts=[
            "Computer-use allows Claude to see the screen via screenshots and control mouse/keyboard",
            "Now available across all API tiers, not just enterprise",
            "Latency is currently higher than human operation — not suited for real-time tasks",
            "Claude approaches tasks cautiously to avoid unintended side-effects",
            "Practical applications: automated testing, form-filling, accessibility tools",
        ],
        key_arguments=[
            "This shifts AI from pure text-generation to active digital labor",
            "The cautious default behavior is a deliberate safety design, not a limitation",
            "Developers should start with narrow, well-defined tasks before broad automation",
        ],
        counterarguments=[
            "Current latency makes it impractical for time-sensitive workflows",
            "Security risks: an AI with desktop control is a significant attack surface",
            "Cost per action is still high for large-scale automation",
        ],
        examples=[
            "Automated UI testing for web apps",
            "Filling out government forms",
            "Monitoring dashboards and sending alerts",
        ],
        sources=[
            ResearchSource(
                title="Anthropic Computer Use Documentation",
                url=None,
                type="article",
                notes="Official documentation — primary source",
            ),
            ResearchSource(
                title="Developer Forum Discussion",
                type="unknown",
                notes="Community observations from early adopters",
            ),
        ],
        short_angles=[
            "5 things you can automate with Claude's computer-use today",
            "The one reason Claude is slower than you at your computer — and why that's fine",
        ],
        long_form_angles=[
            "Complete guide: building your first Claude computer-use agent",
            "Computer-use vs RPA vs traditional automation — what's actually different",
        ],
        documentary_angles=[
            "The road to general-purpose AI agents: from chatbots to desktop control",
        ],
        instagram_angles=[
            "Visual demo: Claude filling out a form autonomously",
            "Carousel: 6 real use-cases for AI computer-use",
        ],
    )
