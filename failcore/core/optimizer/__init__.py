"""
Trace-based Tool Optimizer

Engineering efficiency optimization based on trace analysis.
NOT a security feature - focuses on performance and cost reduction.

Features:
- Detect repeated tool calls (with write barrier awareness)
- Identify redundant parameters
- Suggest caching opportunities (respecting resource mutations)
- Provide actionable optimization advice

NO automatic path changes - only verified suggestions.
NO complex ML - simple pattern matching.

Correctness guarantees:
- Write barriers prevent stale cache suggestions
- Determinism checks ensure safe caching (three-state)
- Resource tracking for accurate analysis (normalized paths)
"""

# Core components
from .detector import PatternDetector
from .cache import CacheAnalyzer
from .advisor import OptimizationAdvisor
from .resources import ResourceIdExtractor, ResourceMutationDetector
from .state import ResourceState, WriteBarrierTracker

# Models (centralized in models.py)
from .models import (
    # Pattern models
    PatternType,
    CallPattern,
    # Cache models
    CacheOpportunity,
    # Suggestion models
    SuggestionType,
    RedundancyStrategy,
    Suggestion,
    # Resource models
    ResourceType,
    MutationType,
)

__all__ = [
    # Core components
    "PatternDetector",
    "CacheAnalyzer",
    "OptimizationAdvisor",
    "ResourceIdExtractor",
    "ResourceMutationDetector",
    "ResourceState",
    "WriteBarrierTracker",
    # Models
    "PatternType",
    "CallPattern",
    "CacheOpportunity",
    "SuggestionType",
    "RedundancyStrategy",
    "Suggestion",
    "ResourceType",
    "MutationType",
]
