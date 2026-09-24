"""Human approval gates — all gates default to requiring human approval."""

from __future__ import annotations

from enum import Enum
from typing import Callable, Optional

from kronos.config import channel_config


class ApprovalGateError(Exception):
    pass


class WorkflowState(Enum):
    TOPIC_APPROVAL = "topic_approval"
    SCRIPT_APPROVAL = "script_approval"
    PRODUCTION_APPROVAL = "production_approval"
    PUBLISH_APPROVAL = "publish_approval"


class ApprovalGate:
    """Manages approval state for a workflow step.

    When mode is 'human', the gate requires an explicit human decision.
    When mode is 'auto', the gate approves automatically (for future automation).
    """

    def __init__(self, state: WorkflowState) -> None:
        self.state = state
        cfg = channel_config().get("approval", {})
        self._mode = cfg.get(state.value, "human")

    def is_auto(self) -> bool:
        return self._mode == "auto"

    def requires_human(self) -> bool:
        return self._mode == "human"

    def request_approval(
        self,
        subject: str,
        context: Optional[str] = None,
        human_callback: Optional[Callable[[str, str], bool]] = None,
    ) -> bool:
        """Request approval. Returns True if approved.

        In auto mode, approves immediately.
        In human mode, calls human_callback if provided; otherwise raises ApprovalGateError.
        """
        if self.is_auto():
            return True

        if human_callback is not None:
            return human_callback(subject, context or "")

        raise ApprovalGateError(
            f"[{self.state.value.upper()}] Human approval required for: {subject}. "
            "Provide a human_callback to handle this gate programmatically."
        )
