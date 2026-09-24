"""Autonomous topic discovery from incoming evidence.

Lightweight normalization + word-overlap clustering; no LLM dependency.
Architecture allows optional AI-assisted semantic clustering later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from delta.models.radar import independent_source_key
from delta.radar.providers.base import SourceEvidence


_STOP_WORDS = {
    "ai", "the", "a", "an", "in", "of", "for", "and", "or", "to", "with",
    "how", "why", "what", "is", "are", "was", "be", "by", "at", "on", "new",
    "best", "top", "my", "i", "you", "your", "this", "that", "it", "from",
    "2024", "2025", "2026", "2027", "vs", "vs.", "just", "now", "these",
    "about", "will", "can", "has", "have", "do", "does",
}

# Keywords that strongly indicate AI/Tech niche
_TECH_AI_KEYWORDS = {
    "llm", "gpt", "claude", "gemini", "llama", "mistral", "openai", "anthropic",
    "agent", "coding", "cursor", "copilot", "chatgpt", "model", "api",
    "automation", "machine", "learning", "neural", "transformer", "diffusion",
    "multimodal", "rag", "vector", "inference", "finetuning", "benchmark",
    "token", "context", "tool", "plugin", "workflow", "developer", "github",
    "programming", "software", "algorithm", "dataset", "training",
}


def _normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _significant_words(text: str) -> set[str]:
    return {
        w for w in _normalize_text(text).split()
        if w not in _STOP_WORDS and len(w) > 2
    }


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class TopicCluster:
    """A group of evidence items discussing the same underlying topic."""

    cluster_id: str
    label: str              # canonical topic label (from first evidence item)
    niche: str              # "ai_tech" | "cross_niche"
    items: list[SourceEvidence] = field(default_factory=list)
    source_ids: set[str] = field(default_factory=set)
    source_types: set[str] = field(default_factory=set)

    def add(self, item: SourceEvidence) -> None:
        if item.source_id not in self.source_ids:
            self.items.append(item)
            self.source_ids.add(item.source_id)
            self.source_types.add(item.source_type)

    @property
    def independent_source_count(self) -> int:
        return len({
            independent_source_key(it.source_type, it.source_id, it.payload)
            for it in self.items
            if it.is_independent
        })


class TopicDiscovery:
    """Extract candidate topic clusters from incoming raw SourceEvidence.

    Algorithm:
      1. Normalize each evidence item's topic_hint.
      2. Extract significant words.
      3. Compute Jaccard similarity against existing cluster labels.
      4. Merge into best-matching cluster if similarity >= threshold.
      5. Otherwise create a new cluster.

    No LLM required. Optional AI-assisted semantic clustering can be added
    later by subclassing or wrapping this class.
    """

    DEFAULT_SIMILARITY_THRESHOLD = 0.20

    def __init__(self, similarity_threshold: Optional[float] = None) -> None:
        self._threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else self.DEFAULT_SIMILARITY_THRESHOLD
        )
        self._cluster_counter = 0

    def discover(self, evidence_items: list[SourceEvidence]) -> list[TopicCluster]:
        """Group evidence items into topic clusters.

        Original evidence provenance is always preserved — merging never
        destroys the source_id, source_type, or payload of any item.
        """
        clusters: list[TopicCluster] = []

        for item in evidence_items:
            hint_words = _significant_words(item.topic_hint)
            best_cluster: Optional[TopicCluster] = None
            best_score = 0.0

            for cluster in clusters:
                label_words = _significant_words(cluster.label)
                score = _jaccard(hint_words, label_words)
                if score > best_score and score >= self._threshold:
                    best_score = score
                    best_cluster = cluster

            if best_cluster is None:
                self._cluster_counter += 1
                best_cluster = TopicCluster(
                    cluster_id=f"cluster_{self._cluster_counter:04d}",
                    label=item.topic_hint,
                    niche=_classify_niche(item.topic_hint),
                )
                clusters.append(best_cluster)

            best_cluster.add(item)

        return clusters

    def to_topic_inputs(
        self,
        clusters: list[TopicCluster],
        min_evidence: int = 1,
    ) -> list[dict]:
        """Convert clusters to RadarPipeline topic_inputs format.

        Includes ``discovery_evidence`` so the pipeline can reuse it instead
        of issuing a second provider fetch for the same topic.
        """
        inputs = []
        for cluster in clusters:
            if len(cluster.items) < min_evidence:
                continue
            inputs.append({
                "topic": cluster.label,
                "niche": cluster.niche,
                "why_now": _build_why_now(cluster),
                "strongest_evidence_summary": _build_evidence_summary(cluster),
                "discovery_evidence": list(cluster.items),
            })
        return inputs


def _classify_niche(topic_hint: str) -> str:
    words = set(_normalize_text(topic_hint).split())
    if words & _TECH_AI_KEYWORDS:
        return "ai_tech"
    return "cross_niche"


def _build_why_now(cluster: TopicCluster) -> str:
    types = ", ".join(sorted(cluster.source_types))
    return (
        f"Signals detected across {cluster.independent_source_count} "
        f"independent source(s) via: {types}."
    )


def _build_evidence_summary(cluster: TopicCluster) -> str:
    count = len(cluster.items)
    types = ", ".join(sorted(cluster.source_types))
    return f"{count} evidence item(s) from {types}."
