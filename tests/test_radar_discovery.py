"""Tests for topic discovery, clustering, and niche classification."""

from datetime import datetime, timezone

import pytest

from delta.radar.discovery import (
    TopicCluster,
    TopicDiscovery,
    _classify_niche,
    _jaccard,
    _significant_words,
)
from delta.radar.providers.base import SourceEvidence


def _utc() -> datetime:
    return datetime.now(timezone.utc)


def make_evidence(
    topic_hint: str,
    source_id: str = "id_1",
    source_type: str = "youtube",
) -> SourceEvidence:
    return SourceEvidence(
        topic_hint=topic_hint,
        source_type=source_type,
        source_id=source_id,
        observed_at=_utc(),
        evidence_type="youtube_video",
        payload={},
        is_independent=True,
    )


# --- _significant_words ---

def test_significant_words_removes_stop_words():
    words = _significant_words("the AI model release 2026")
    assert "the" not in words
    assert "2026" not in words
    assert "model" in words
    assert "release" in words


def test_significant_words_filters_short_words():
    words = _significant_words("a b cd large")
    # 'a' and 'b' (len 1) removed; 'cd' (len 2) removed
    assert "a" not in words
    assert "b" not in words
    assert "cd" not in words
    assert "large" in words


# --- _jaccard ---

def test_jaccard_identical_sets():
    assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint_sets():
    assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0


def test_jaccard_partial_overlap():
    score = _jaccard({"a", "b", "c"}, {"b", "c", "d"})
    assert 0 < score < 1.0


def test_jaccard_empty_sets():
    assert _jaccard(set(), {"a"}) == 0.0
    assert _jaccard({"a"}, set()) == 0.0


# --- _classify_niche ---

def test_classify_niche_ai_tech():
    assert _classify_niche("Claude AI coding agent") == "ai_tech"
    assert _classify_niche("new LLM benchmark 2026") == "ai_tech"
    assert _classify_niche("GPT model release") == "ai_tech"


def test_classify_niche_cross_niche():
    assert _classify_niche("global tariff impact small business") == "cross_niche"
    assert _classify_niche("sports championship results") == "cross_niche"


# --- TopicDiscovery ---

def test_single_item_creates_one_cluster():
    disc = TopicDiscovery()
    ev = make_evidence("Claude AI coding agent", "id_1")
    clusters = disc.discover([ev])
    assert len(clusters) == 1
    assert clusters[0].label == "Claude AI coding agent"


def test_similar_topics_merge_into_one_cluster():
    disc = TopicDiscovery(similarity_threshold=0.10)
    items = [
        make_evidence("Claude AI coding assistant", "id_1"),
        make_evidence("Claude AI coding tool", "id_2"),
    ]
    clusters = disc.discover(items)
    assert len(clusters) == 1
    assert len(clusters[0].items) == 2


def test_different_topics_create_separate_clusters():
    disc = TopicDiscovery(similarity_threshold=0.25)
    items = [
        make_evidence("Claude AI coding agent", "id_1"),
        make_evidence("global tariff small business", "id_2"),
    ]
    clusters = disc.discover(items)
    assert len(clusters) == 2


def test_provenance_preserved_after_clustering():
    disc = TopicDiscovery(similarity_threshold=0.10)
    ev1 = make_evidence("Claude AI coding assistant", "id_1", "youtube")
    ev2 = make_evidence("Claude AI coding tool", "id_2", "news")
    clusters = disc.discover([ev1, ev2])
    cluster = clusters[0]
    source_types = {it.source_type for it in cluster.items}
    assert "youtube" in source_types
    assert "news" in source_types


def test_duplicate_source_id_not_added_twice():
    disc = TopicDiscovery()
    ev = make_evidence("Claude AI coding", "same_id")
    clusters = disc.discover([ev, ev])
    # second add is deduped by source_id
    assert len(clusters[0].items) == 1


def test_cluster_niche_classification():
    disc = TopicDiscovery()
    ev_tech = make_evidence("new LLM model release", "id_1")
    ev_other = make_evidence("football championship 2026", "id_2")
    clusters = disc.discover([ev_tech, ev_other])
    niches = {c.niche for c in clusters}
    assert "ai_tech" in niches
    assert "cross_niche" in niches


def test_independent_source_count():
    disc = TopicDiscovery(similarity_threshold=0.10)
    items = [
        make_evidence("Claude coding", "id_1", "youtube"),
        make_evidence("Claude coding", "id_2", "news"),
        make_evidence("Claude coding", "id_3", "youtube"),
    ]
    clusters = disc.discover(items)
    assert clusters[0].independent_source_count == 3


def test_to_topic_inputs_min_evidence_filter():
    disc = TopicDiscovery()
    ev = make_evidence("Claude AI", "id_1")
    clusters = disc.discover([ev])
    inputs_1 = disc.to_topic_inputs(clusters, min_evidence=1)
    inputs_2 = disc.to_topic_inputs(clusters, min_evidence=2)
    assert len(inputs_1) == 1
    assert len(inputs_2) == 0


def test_to_topic_inputs_structure():
    disc = TopicDiscovery()
    ev = make_evidence("Claude AI coding agent", "id_1")
    clusters = disc.discover([ev])
    inputs = disc.to_topic_inputs(clusters, min_evidence=1)
    assert len(inputs) == 1
    inp = inputs[0]
    assert "topic" in inp
    assert "niche" in inp
    assert "why_now" in inp
    assert "strongest_evidence_summary" in inp


def test_multiple_runs_accumulate_counter():
    disc = TopicDiscovery()
    ev1 = make_evidence("topic alpha", "id_1")
    ev2 = make_evidence("topic beta", "id_2")
    c1 = disc.discover([ev1])
    c2 = disc.discover([ev2])
    assert c1[0].cluster_id != c2[0].cluster_id


def test_source_types_tracked_on_cluster():
    disc = TopicDiscovery(similarity_threshold=0.10)
    items = [
        make_evidence("Claude AI", "id_1", "youtube"),
        make_evidence("Claude AI news", "id_2", "news"),
    ]
    clusters = disc.discover(items)
    assert "youtube" in clusters[0].source_types
    assert "news" in clusters[0].source_types
