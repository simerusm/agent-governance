"""
Runtime layer for governed agent execution.

This layer defines what a governed run is (lifecycle, hooks, policy evaluation, actions),
while delegating *where* execution happens to an abstract backend.
"""

from .decision_engine import Decision, DecisionAction
from .execution_context import ExecutionContext, LLMClient, MockLLM
from .hooks import Hook, HookEvent
from .policies import RuntimePolicy
from .runner import (
    CloudExecutionBackend,
    ExecutionBackend,
    GovernedRunner,
    LocalExecutionBackend,
)
from .trace_capture import TraceCollector

__all__ = [
    "CloudExecutionBackend",
    "Decision",
    "DecisionAction",
    "ExecutionBackend",
    "ExecutionContext",
    "GovernedRunner",
    "Hook",
    "HookEvent",
    "LLMClient",
    "LocalExecutionBackend",
    "MockLLM",
    "RuntimePolicy",
    "TraceCollector",
]

