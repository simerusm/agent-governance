"""
Thin developer SDK for governed agent runs: decorators, runtime client hooks, context.

This package does not start infrastructure; it registers metadata and delegates execution
to a pluggable :class:`RuntimeClient`.
"""

from .artifacts import ArtifactRef, record_artifact
from .client import (
    DefaultRuntimeClient,
    HttpReportingClient,
    RuntimeClient,
    RuntimeLayerClient,
    build_client_from_config,
)
from .config import GovernanceConfig, load_config
from .context import AgentMetadata, RunContext, current_run_context, run_context, with_run_context
from .decorators import get_default_client, governed_agent, set_default_client
from .tooling import file_reference, record_tool_invocation

__all__ = [
    "AgentMetadata",
    "ArtifactRef",
    "DefaultRuntimeClient",
    "GovernanceConfig",
    "HttpReportingClient",
    "RuntimeClient",
    "RuntimeLayerClient",
    "RunContext",
    "build_client_from_config",
    "current_run_context",
    "file_reference",
    "get_default_client",
    "governed_agent",
    "load_config",
    "record_artifact",
    "record_tool_invocation",
    "run_context",
    "set_default_client",
    "with_run_context",
]
