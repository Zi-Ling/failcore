"""
Optimizer Data Models

Centralized model definitions for optimizer components
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List
from enum import Enum


# =============================================================================
# Pattern Detection Models
# =============================================================================

class PatternType(str, Enum):
    """Pattern types"""
    REPEATED_CALL = "repeated_call"          # Same tool+params called multiple times
    REDUNDANT_PARAMS = "redundant_params"    # Parameters that don't affect output
    SEQUENTIAL_READS = "sequential_reads"    # Sequential file reads (could batch)
    WRITE_READ_CYCLE = "write_read_cycle"    # Write then immediately read
    CACHE_MISS = "cache_miss"                # Could have been cached


@dataclass
class CallPattern:
    """
    Detected call pattern
    """
    pattern_type: PatternType
    tool_name: str
    occurrences: int
    step_ids: List[str] = field(default_factory=list)
    params_sample: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_description(self) -> str:
        """Get human-readable description"""
        if self.pattern_type == PatternType.REPEATED_CALL:
            return f"{self.tool_name} called {self.occurrences} times with identical parameters"
        elif self.pattern_type == PatternType.REDUNDANT_PARAMS:
            redundant = self.metadata.get("redundant_params", [])
            return f"{self.tool_name} has redundant parameters: {', '.join(redundant)}"
        elif self.pattern_type == PatternType.SEQUENTIAL_READS:
            return f"{self.occurrences} sequential reads in {self.tool_name} - consider batching"
        elif self.pattern_type == PatternType.WRITE_READ_CYCLE:
            return f"Write-read cycle detected in {self.tool_name}"
        elif self.pattern_type == PatternType.CACHE_MISS:
            return f"{self.tool_name} result could have been cached"
        return f"Pattern: {self.pattern_type.value}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        return {
            "pattern_type": self.pattern_type.value,
            "tool_name": self.tool_name,
            "occurrences": self.occurrences,
            "step_ids": self.step_ids,
            "description": self.get_description(),
            "metadata": self.metadata,
        }


# =============================================================================
# Cache Analysis Models
# =============================================================================

@dataclass
class CacheOpportunity:
    """
    Caching opportunity
    
    Represents a tool call that could benefit from caching
    """
    tool_name: str
    params: Dict[str, Any]
    call_count: int  # Number of times this call was made
    step_ids: List[str] = field(default_factory=list)
    estimated_savings: float = 0.0  # Estimated time/cost savings
    cache_key: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_description(self) -> str:
        """Get human-readable description"""
        return f"{self.tool_name} called {self.call_count}x - cache could save {self.call_count - 1} calls"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        return {
            "tool_name": self.tool_name,
            "call_count": self.call_count,
            "estimated_savings": self.estimated_savings,
            "description": self.get_description(),
            "cache_key": self.cache_key,
            "metadata": self.metadata,
        }


# =============================================================================
# Suggestion Models
# =============================================================================

class SuggestionType(str, Enum):
    """
    Unified suggestion type
    
    All suggestions are about eliminating REDUNDANCY.
    The 'strategy' field differentiates the approach.
    """
    REDUNDANCY = "redundancy"  # Eliminate redundancy (use strategy field for details)


class RedundancyStrategy(str, Enum):
    """Redundancy elimination strategies"""
    DEDUPE = "dedupe"                # Deduplicate identical calls
    CACHE = "cache"                  # Cache results
    COALESCE = "coalesce"            # Merge/batch multiple calls
    REORDER = "reorder"              # Reorder to eliminate redundancy
    SIMPLIFY = "simplify"            # Simplify parameters


@dataclass
class Suggestion:
    """
    Optimization suggestion
    
    Actionable, verifiable recommendation
    
    All suggestions are about eliminating REDUNDANCY.
    Use 'strategy' to differentiate approaches.
    """
    suggestion_type: SuggestionType
    strategy: str  # RedundancyStrategy value (dedupe/cache/coalesce/reorder/simplify)
    title: str
    description: str
    impact: str  # Expected impact (e.g., "Save 3 calls", "Reduce latency by 30%")
    confidence: float  # 0.0 - 1.0
    action: str  # Concrete action to take
    affected_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        return {
            "suggestion_type": self.suggestion_type.value,
            "strategy": self.strategy,
            "title": self.title,
            "description": self.description,
            "impact": self.impact,
            "confidence": self.confidence,
            "action": self.action,
            "affected_steps": self.affected_steps,
            "metadata": self.metadata,
        }


# =============================================================================
# Resource Models
# =============================================================================

class ResourceType(str, Enum):
    """Resource types"""
    FILE = "file"
    HTTP = "http"
    DATABASE = "database"
    MEMORY = "memory"
    UNKNOWN = "unknown"


class MutationType(str, Enum):
    """Mutation types"""
    WRITE = "write"      # Create or update
    DELETE = "delete"    # Remove
    RENAME = "rename"    # Move/rename
    APPEND = "append"    # Append to existing


__all__ = [
    # Pattern models
    "PatternType",
    "CallPattern",
    # Cache models
    "CacheOpportunity",
    # Suggestion models
    "SuggestionType",
    "RedundancyStrategy",
    "Suggestion",
    # Resource models
    "ResourceType",
    "MutationType",
]
