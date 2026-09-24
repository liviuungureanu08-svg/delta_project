"""Tests for approval gates."""

import pytest
from delta.config import reload_all
from delta.workflow import ApprovalGate, ApprovalGateError, WorkflowState


@pytest.fixture(autouse=True)
def clear_cache():
    reload_all()
    yield
    reload_all()


def test_human_gate_requires_callback():
    gate = ApprovalGate(WorkflowState.TOPIC_APPROVAL)
    assert gate.requires_human()
    with pytest.raises(ApprovalGateError):
        gate.request_approval("topic", "context")


def test_human_gate_with_callback_approves():
    gate = ApprovalGate(WorkflowState.SCRIPT_APPROVAL)
    result = gate.request_approval("topic", "context", human_callback=lambda s, c: True)
    assert result is True


def test_human_gate_with_callback_rejects():
    gate = ApprovalGate(WorkflowState.PRODUCTION_APPROVAL)
    result = gate.request_approval("topic", "context", human_callback=lambda s, c: False)
    assert result is False


def test_all_gates_default_to_human():
    for state in WorkflowState:
        gate = ApprovalGate(state)
        assert gate.requires_human(), f"{state.value} should default to human"
