"""Operation classes and weighted cost units for rate limiting.

Different API operations have radically different cost profiles.
A plain RPM limit does not account for the difference between reading a run
and triggering a full Arena with judging, synthesis, and verification.
"""

from enum import Enum
from typing import Dict


class OperationClass(str, Enum):
    """Classification of API operations by cost weight."""

    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


# Weighted cost units per operation class
# A continuation or full Debate should consume more budget than a provider-key validation.
OPERATION_WEIGHTS: Dict[OperationClass, int] = {
    OperationClass.LIGHT: 1,
    OperationClass.MEDIUM: 3,
    OperationClass.HEAVY: 8,
}


# Operation class mapping for specific endpoints/actions
OPERATION_CLASSES: Dict[str, OperationClass] = {
    # Light: reads, list, search
    "read_run": OperationClass.LIGHT,
    "list_runs": OperationClass.LIGHT,
    "search": OperationClass.LIGHT,
    "read_report": OperationClass.LIGHT,
    "get_debate": OperationClass.LIGHT,
    "get_events": OperationClass.LIGHT,
    "get_members": OperationClass.LIGHT,
    # Medium: validate, retry single, export
    "validate_provider_key": OperationClass.MEDIUM,
    "retry_single_model": OperationClass.MEDIUM,
    "export_report": OperationClass.MEDIUM,
    "retry_agent": OperationClass.MEDIUM,
    # Heavy: create, continue, rerun judging/synthesis
    "create_arena": OperationClass.HEAVY,
    "create_debate": OperationClass.HEAVY,
    "continue_staged_run": OperationClass.HEAVY,
    "rerun_judging": OperationClass.HEAVY,
    "rerun_synthesis": OperationClass.HEAVY,
    "debate_continue": OperationClass.HEAVY,
    "debate_retry": OperationClass.HEAVY,
}


def get_operation_class(action: str) -> OperationClass:
    """Get the operation class for a given action name."""
    return OPERATION_CLASSES.get(action, OperationClass.MEDIUM)


def get_operation_weight(action: str) -> int:
    """Get the weighted cost units for a given action."""
    op_class = get_operation_class(action)
    return OPERATION_WEIGHTS[op_class]
