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

        for topic_input in topic_inputs:
            topic = topic_input["topic"]
            niche = topic_input.get("niche", "ai_tech")

            # Collect evidence from all providers
            all_evidence: list[Evidence] = []
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

            # Preliminary scoring (needed by Stage 2)
            candidate = self._scoring.score(candidate)

            # Stage 2: validation
            candidate = self._stage2.process(candidate)

            # Re-score after validation (signals may have been refined)
            candidate = self._scoring.score(candidate)

            candidates.append(candidate)

        return self._top5.select(candidates)
