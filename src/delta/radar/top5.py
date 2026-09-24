"""Top 5 selector — picks the daily maximum 5 opportunities for human approval."""

from __future__ import annotations

from datetime import datetime, timezone

from delta.models.radar import (
    DailyTop5, LifecycleState, MomentumState, OpportunityReport, RadarCandidate,
)


_LIFECYCLE_RANK = {
    LifecycleState.HUMAN_APPROVAL: 5,
    LifecycleState.TOP_5: 4,
    LifecycleState.VALIDATED: 3,
    LifecycleState.WATCH: 2,
    LifecycleState.DISCOVERED: 1,
    LifecycleState.REJECTED: 0,
}


class Top5Selector:
    """Selects at most 5 VALIDATED candidates ranked by opportunity score."""

    MAX_CANDIDATES = 5

    def __init__(self, radar_cfg: dict) -> None:
        top5_cfg = radar_cfg["top5"]
        self._min_lifecycle_str = top5_cfg.get("min_lifecycle", "VALIDATED")
        self._min_opportunity = top5_cfg.get("min_opportunity_score", 0.40)
        self._min_confidence = top5_cfg.get("min_confidence_score", 0.30)
        min_lc = LifecycleState[self._min_lifecycle_str]
        self._min_lifecycle_rank = _LIFECYCLE_RANK[min_lc]

    def select(self, candidates: list[RadarCandidate]) -> DailyTop5:
        """Select the daily top 5 from a list of candidates."""
        eligible = [
            c for c in candidates
            if _LIFECYCLE_RANK.get(c.lifecycle, 0) >= self._min_lifecycle_rank
            and c.opportunity_score >= self._min_opportunity
            and c.confidence_score >= self._min_confidence
        ]

        # Sort: opportunity_score descending, confidence_score as tiebreaker
        eligible.sort(
            key=lambda c: (c.opportunity_score, c.confidence_score),
            reverse=True,
        )

        selected = eligible[: self.MAX_CANDIDATES]

        reports: list[OpportunityReport] = []
        for candidate in selected:
            candidate.lifecycle = LifecycleState.HUMAN_APPROVAL
            report = self._to_report(candidate)
            reports.append(report)

        rejected_count = len(candidates) - len(selected)

        return DailyTop5(
            generated_at=datetime.now(timezone.utc),
            reports=reports,
            candidates_evaluated=len(candidates),
            candidates_rejected=rejected_count,
        )

    def rejection_reason(self, candidate: RadarCandidate) -> str:
        """Explain why a non-selected candidate did not enter the Top 5.

        Read-only mirror of the eligibility filter in select(); used for diagnostics.
        """
        reasons: list[str] = []
        if _LIFECYCLE_RANK.get(candidate.lifecycle, 0) < self._min_lifecycle_rank:
            stage = (
                "Stage 1: no fresh independent evidence"
                if candidate.lifecycle == LifecycleState.DISCOVERED
                else f"Stage 2: {candidate.main_risk or 'not validated'}"
            )
            reasons.append(
                f"Lifecycle {candidate.lifecycle.value} < {self._min_lifecycle_str} ({stage})"
            )
        if candidate.opportunity_score < self._min_opportunity:
            reasons.append(
                f"Opportunity score {candidate.opportunity_score:.3f} < {self._min_opportunity}"
            )
        if candidate.confidence_score < self._min_confidence:
            reasons.append(
                f"Confidence score {candidate.confidence_score:.3f} < {self._min_confidence}"
            )
        if not reasons:
            reasons.append(f"Eligible but ranked below top {self.MAX_CANDIDATES}")
        return "; ".join(reasons)

    def _to_report(self, candidate: RadarCandidate) -> OpportunityReport:
        formats = self._recommend_formats(candidate)
        return OpportunityReport(
            topic=candidate.topic,
            niche=candidate.niche,
            lifecycle=LifecycleState.HUMAN_APPROVAL,
            opportunity_score=candidate.opportunity_score,
            confidence_score=candidate.confidence_score,
            momentum_state=candidate.momentum_state,
            saturation_state=candidate.saturation_state,
            why_now=candidate.why_now or "Trending signals detected across multiple sources.",
            strongest_evidence=candidate.strongest_evidence_summary or (
                f"{candidate.signals.independent_source_count} independent source(s), "
                f"momentum: {candidate.signals.momentum.value}"
            ),
            main_risk=candidate.main_risk or "Verify evidence freshness before production.",
            recommended_formats=formats,
            suggested_angle=self._suggest_angle(candidate),
            human_approved=None,  # always pending until human decides
        )

    def _recommend_formats(self, candidate: RadarCandidate) -> list[str]:
        formats = []
        score = candidate.opportunity_score
        fresh = (candidate.signals.freshness_days or 99) <= 3

        if fresh and score >= 0.50:
            formats.append("SHORT")
        if score >= 0.50:
            formats.append("UTILITY_LONG_FORM")
        if score >= 0.65:
            formats.append("INSTAGRAM_POST")
        if score >= 0.70:
            formats.append("INSTAGRAM_CAROUSEL")
        if score >= 0.75:
            formats.append("DOCUMENTARY")

        return formats or ["UTILITY_LONG_FORM"]

    def _suggest_angle(self, candidate: RadarCandidate) -> str:
        niche = candidate.niche
        momentum = candidate.signals.momentum

        if niche == "cross_niche":
            return (
                f"How {candidate.topic} affects the tech/AI audience — "
                "connect to our niche via practical impact."
            )

        if momentum == MomentumState.ACCELERATING:
            return f"Why {candidate.topic} is changing everything right now — be first."
        if momentum == MomentumState.RISING:
            return f"What you need to know about {candidate.topic} before it explodes."
        return f"Deep dive: {candidate.topic} explained clearly."
