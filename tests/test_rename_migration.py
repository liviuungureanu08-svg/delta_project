"""Tests verifying Kronos → Delta migration integrity."""

import importlib
import sys


def test_delta_package_importable():
    import delta
    assert delta.__version__ == "0.2.0"


def test_delta_models_importable():
    from delta.models import (
        TopicCandidate, DemandIndicators, CompetitionIndicators,
        MasterResearch, ResearchSource,
        ContentPlan, ContentSection, ApprovalStatus,
        RetentionPlan, TimelineSegment, AssetType,
        ProductionBudget, AssetCost,
    )
    assert TopicCandidate is not None


def test_delta_radar_models_importable():
    from delta.models import (
        Evidence, Signals, LifecycleState, SaturationState, MomentumState,
        RadarCandidate, OpportunityReport, DailyTop5,
    )
    assert LifecycleState.DISCOVERED is not None


def test_delta_engine_importable():
    from delta.engine import OpportunityEngine, ContentPlanner, RetentionBuilder, CostController
    assert OpportunityEngine is not None


def test_delta_workflow_importable():
    from delta.workflow import ApprovalGate, WorkflowState, ApprovalGateError
    assert WorkflowState.TOPIC_APPROVAL is not None


def test_delta_providers_importable():
    from delta.providers import MockVideoProvider, MockImageProvider, MockTTSProvider
    assert MockVideoProvider is not None


def test_delta_radar_importable():
    from delta.radar import (
        Stage1Discovery, Stage2Validation, RadarScoring,
        SaturationClassifier, Top5Selector, RadarPipeline,
    )
    assert RadarPipeline is not None


def test_delta_config_has_radar():
    from delta.config import radar_config, reload_all
    reload_all()
    cfg = radar_config()
    assert "radar" in cfg
    reload_all()


def test_kronos_naming_absent_in_delta_source():
    """Verify no stray 'kronos' module references in delta source files."""
    import delta
    from pathlib import Path
    delta_src = Path(delta.__file__).parent
    for py_file in delta_src.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        # Allow "kronos" in comments/strings, but flag module imports
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'"):
                continue
            assert "from kronos" not in stripped, (
                f"Stray kronos import in {py_file}: {line!r}"
            )
            assert "import kronos" not in stripped, (
                f"Stray kronos import in {py_file}: {line!r}"
            )
