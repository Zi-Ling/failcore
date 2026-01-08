# failcore/core/egress/__init__.py
"""
Egress - Unified execution chokepoint

All real-world side effects flow through EgressEngine.
Entry points (MCP/Proxy/SDK) → EgressEvent → Engine → Sinks/Enrichers
"""

from .types import EgressEvent, EgressType, PolicyDecision, RiskLevel
from .policy import normalize_policy_decision
from .engine import EgressEngine
from .sinks import TraceSink
from .enrichers import UsageEnricher, DLPEnricher, TaintEnricher
from .adapters import EgressTraceRecorder

__all__ = [
    "EgressEvent",
    "EgressType",
    "PolicyDecision",
    "RiskLevel",
    "normalize_policy_decision",
    "EgressEngine",
    "TraceSink",
    "UsageEnricher",
    "DLPEnricher",
    "TaintEnricher",
    "EgressTraceRecorder",
]
