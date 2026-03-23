"""
ToolCallControl — deterministic tool-calling control plane for agent loops.

The model **proposes**; the control plane **decides**, **executes** (server or client
venue), and **logs** every step. See ``ARCHITECTURE.md`` in the repository for the full design.
"""

from .aggregator import NoConsensus, majority_aggregate
from .classifier import CallableClassifier, Classifier, MockClassifier
from .constraint_pipeline import ConstraintPipeline
from .event_log import EventLog
from .exceptions import ClassificationError, ExecutionError, ToolCallControlError, UnknownToolError
from .executor import execute
from .loop import LoopRunner
from .model import (
    AggregateMode,
    ClassificationResult,
    Decision,
    Event,
    ProfileConfig,
    Proposal,
    Session,
    ToolDef,
    Venue,
)
from .openai_classifier import OpenAIClassifier
from .policy import ClassificationPolicyRegistry, PolicyRule
from .profiles import (
    dump_profile_bundle,
    dump_profile_file,
    load_profile_bundle,
    load_profile_file,
    profile_from_json,
    profile_to_json,
)
from .proposer import MockProposer, Proposer, propose
from .tool_registry import ToolRegistry, demo_tools
from .trace import count_tags_from_events, trace_deficits, trace_requirements_met

__version__ = "0.2.2"

__all__ = [
    "AggregateMode",
    "ClassificationPolicyRegistry",
    "ClassificationResult",
    "CallableClassifier",
    "ClassificationError",
    "Classifier",
    "ConstraintPipeline",
    "Decision",
    "Event",
    "EventLog",
    "ExecutionError",
    "LoopRunner",
    "MockClassifier",
    "MockProposer",
    "NoConsensus",
    "OpenAIClassifier",
    "Proposer",
    "PolicyRule",
    "ProfileConfig",
    "Proposal",
    "Session",
    "ToolCallControlError",
    "ToolDef",
    "ToolRegistry",
    "UnknownToolError",
    "Venue",
    "count_tags_from_events",
    "trace_deficits",
    "trace_requirements_met",
    "demo_tools",
    "dump_profile_bundle",
    "dump_profile_file",
    "load_profile_bundle",
    "load_profile_file",
    "profile_from_json",
    "profile_to_json",
    "execute",
    "majority_aggregate",
    "propose",
]
