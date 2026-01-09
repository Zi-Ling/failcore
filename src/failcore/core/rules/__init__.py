"""
Core Rules - Neutral decision rules layer

This layer contains shared rule definitions used by both gates and enrichers.
It is dependency-neutral and sits below both guards and enrichers.

Architecture:
- rules/dlp     - DLP pattern definitions
- rules/semantic - Semantic rule definitions  
- rules/effects  - Side-effect type definitions
- rules/schemas  - Unified field schemas

Design principles:
1. Rules are declarative data, not execution logic
2. Both gates (decision) and enrichers (evidence) use same rules
3. No dependencies on guards or enrichers
4. Version-controlled rule definitions
"""

from .dlp import DLPPatternRegistry, SensitivePattern, PatternCategory
from .semantic import SemanticRule, RuleCategory, RuleSeverity, RuleRegistry
from .effects import SideEffectType, SideEffectCategory
from .schemas import TargetSchema, VerdictSchema, EvidenceSchema

__all__ = [
    # DLP
    "DLPPatternRegistry",
    "SensitivePattern", 
    "PatternCategory",
    # Semantic
    "SemanticRule",
    "RuleCategory",
    "RuleSeverity",
    "RuleRegistry",
    # Effects
    "SideEffectType",
    "SideEffectCategory",
    # Schemas
    "TargetSchema",
    "VerdictSchema",
    "EvidenceSchema",
]
