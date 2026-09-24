"""Radar pipeline — full daily analysis: evidence → discovery → validation → top 5."""

from __future__ import annotations

from datetime import datetime, timezone

from delta.config import radar_config
from delta.models.radar import DailyTop5, Evidence, LifecycleState, RadarCandidate
from delta.radar.providers.base import RadarSourceProvider, SourceEvidence
from delta.radar.scoring import RadarScoring
from delta.radar.signals import evidence_from_source
from delta.radar.stage1 import Stage1Discovery
from delta.radar.stage2 import Stage2Validation
from delta.radar.top5 import Top5Selector


class RadarPipeline:
    """Orchestrates daily opportunity analysis.

    Usage:
        pipeline = RadarPipeline()
        top5 = pipeline.run(topics, providers)
    """

    def __init__(self, cfg: dict | None = None) -> None:
        self._cfg = cfg if cfg is not None else radar_config()["radar"]
        self._stage1 = Stage1Discovery(self._cfg)
        self._scoring = RadarScoring(self._cfg)
        self._stage2 = Stage2Validation(self._cfg)
        self._top5 = Top5Selector(self._cfg)
        # Per-candidate diagnostics from the most recent run() (read-only record).
        self.last_candidate_diagnostics: list[dict] = []

    def run(
        self,
        topic_inputs: list[dict],
        providers: list[RadarSourceProvider],
    ) -> DailyTop5:
        """Run a full daily analysis.

        Args:
            topic_inputs: list of dicts with keys:
                - topic (str): topic label
                - niche (str): "ai_tech" | "cross_niche"
                - why_now (str, optional)
                - strongest_evidence_summary (str, optional)
            providers: list of RadarSourceProvider instances to collect evidence from

        Returns:
            DailyTop5 with at most 5 human-approval-pending opportunity reports.
        """
        candidates: list[RadarCandidate] = []
        stage_lifecycles: list[tuple[str, str]] = []

        for topic_input in topic_inputs:
            topic = topic_input["topic"]
            niche = topic_input.get("niche", "ai_tech")

            # Reuse evidence already fetched during discovery when available;
            # otherwise collect fresh evidence from providers.
            prefetched: list[SourceEvidence] = topic_input.get("discovery_evidence") or []
            all_evidence: list[Evidence] = [evidence_from_source(se) for se in prefetched]
            if not all_evidence:
                for provider in providers:
                    raw: list[SourceEvidence] = provider.fetch_evidence([topic])
                    for se in raw:
                        all_evidence.append(evidence_from_source(se))

            candidate = RadarCandidate(
                topic=topic,
                niche=niche,
                evidence=all_evidence,
                why_now=topic_input.get("why_now"),
                strongest_evidence_summary=topic_input.get("strongest_evidence_summary"),
            )

            # Stage 1: sensitive discovery
            candidate = self._stage1.process(candidate)
            lifecycle_stage1 = candidate.lifecycle.value

            # Preliminary scoring (needed by Stage 2)
            candidate = self._scoring.score(candidate)

            # Stage 2: validation
            candidate = self._stage2.process(candidate)
            lifecycle_stage2 = candidate.lifecycle.value

            # Re-score after validation (signals may have been refined)
            candidate = self._scoring.score(candidate)

            candidates.append(candidate)
            stage_lifecycles.append((lifecycle_stage1, lifecycle_stage2))

        top5 = self._top5.select(candidates)
        self.last_candidate_diagnostics = [
            self._candidate_diagnostics(c, s1, s2)
            for c, (s1, s2) in zip(candidates, stage_lifecycles)
        ]
        return top5

    def _candidate_diagnostics(
        self, candidate: RadarCandidate, lifecycle_stage1: str, lifecycle_stage2: str
    ) -> dict:
        source_types: dict[str, int] = {}
        for ev in candidate.evidence:
            source_types[ev.source_type] = source_types.get(ev.source_type, 0) + 1
        selected = candidate.lifecycle == LifecycleState.HUMAN_APPROVAL
        return {
            "topic": candidate.topic,
            "niche": candidate.niche,
            "evidence_source_types": source_types,
            "evidence_item_count": len(candidate.evidence),
            "independent_source_count": candidate.signals.independent_source_count,
            "opportunity_score": candidate.opportunity_score,
            "confidence_score": candidate.confidence_score,
            "momentum": candidate.momentum_state.value,
            "saturation": candidate.saturation_state.value,
            "freshness_days": candidate.signals.freshness_days,
            "lifecycle_after_stage1": lifecycle_stage1,
            "lifecycle_after_stage2": lifecycle_stage2,
            "selected_for_top5": selected,
            "main_risk": candidate.main_risk,
            "rejection_reason": (
                None if selected else self._top5.rejection_reason(candidate)
            ),
        }
