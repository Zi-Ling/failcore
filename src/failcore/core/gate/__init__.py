"""
Core Gate - Abstract gate interface

Gate is the authoritative decision point that writes VERDICT.
There are two types of gates:
1. Preflight Gate - at tool call boundary (guards implementation)
2. Egress Gate - at proxy/network boundary (proxy implementation)

Architecture principles:
1. Gate is the ONLY entity that can write VERDICT
2. Both gate types share same decision semantics
3. Both produce homogeneous ATTEMPT events
4. Decision based on shared rules (core/rules)

This design solves "proxy mode losing blocking capability" problem by
elevating decision authority from "guards" to abstract "Gate".
"""

from .interface import Gate, GateVerdict, GateContext
from .preflight import PreflightGate
from .egress import EgressGate

__all__ = [
    "Gate",
    "GateVerdict",
    "GateContext",
    "PreflightGate",
    "EgressGate",
]
