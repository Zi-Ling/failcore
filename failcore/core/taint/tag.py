"""
Taint Tracking - Tag Models

Lightweight data tainting at tool boundaries (not full dataflow analysis)
"""

from dataclasses import dataclass, field
from typing import Set, Optional, Any, Dict
from datetime import datetime, timezone
from enum import Enum


class TaintSource(str, Enum):
    """Taint source types"""
    FILE = "file"                # File read
    DATABASE = "database"        # Database query
    API = "api"                  # External API
    USER_INPUT = "user_input"    # User-provided data
    ENVIRONMENT = "environment"  # Environment variables
    SECRET = "secret"            # Secret/credential


class DataSensitivity(str, Enum):
    """Data sensitivity classification"""
    PUBLIC = "public"            # Public data
    INTERNAL = "internal"        # Internal use only
    CONFIDENTIAL = "confidential"  # Confidential
    SECRET = "secret"            # Secret/highly sensitive
    PII = "pii"                  # Personally Identifiable Information


@dataclass
class TaintTag:
    """
    Taint tag for data tracking
    
    Attached to data as it flows through tools
    """
    # Source identification
    source: TaintSource
    source_tool: str  # Tool that produced this data
    source_step_id: str
    
    # Sensitivity classification
    sensitivity: DataSensitivity = DataSensitivity.INTERNAL
    
    # Data classification
    contains_pii: bool = False
    contains_secrets: bool = False
    contains_customer_data: bool = False
    
    # Metadata
    tagged_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reason: str = ""
    
    # Context
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self) -> int:
        """Make TaintTag hashable for use in sets"""
        # Hash based on immutable identifying fields
        return hash((
            self.source,
            self.source_tool,
            self.source_step_id,
            self.sensitivity,
            self.contains_pii,
            self.contains_secrets,
            self.contains_customer_data,
            self.reason,
        ))
    
    def __eq__(self, other) -> bool:
        """Equality based on identifying fields"""
        if not isinstance(other, TaintTag):
            return False
        return (
            self.source == other.source
            and self.source_tool == other.source_tool
            and self.source_step_id == other.source_step_id
            and self.sensitivity == other.sensitivity
            and self.contains_pii == other.contains_pii
            and self.contains_secrets == other.contains_secrets
            and self.contains_customer_data == other.contains_customer_data
            and self.reason == other.reason
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        return {
            "source": self.source.value,
            "source_tool": self.source_tool,
            "source_step_id": self.source_step_id,
            "sensitivity": self.sensitivity.value,
            "contains_pii": self.contains_pii,
            "contains_secrets": self.contains_secrets,
            "contains_customer_data": self.contains_customer_data,
            "tagged_at": self.tagged_at,
            "reason": self.reason,
            "metadata": self.metadata,
        }


@dataclass
class TaintedData:
    """
    Container for tainted data
    
    Wraps actual data with taint tags
    """
    data: Any
    tags: Set[TaintTag] = field(default_factory=set)
    
    def add_tag(self, tag: TaintTag) -> None:
        """Add taint tag"""
        self.tags.add(tag)
    
    def has_tag(self, source: TaintSource = None, sensitivity: DataSensitivity = None) -> bool:
        """Check if has specific tag"""
        for tag in self.tags:
            if source and tag.source != source:
                continue
            if sensitivity and tag.sensitivity != sensitivity:
                continue
            return True
        return False
    
    def max_sensitivity(self) -> Optional[DataSensitivity]:
        """Get maximum sensitivity level"""
        if not self.tags:
            return None
        
        # Sensitivity hierarchy
        hierarchy = {
            DataSensitivity.PUBLIC: 0,
            DataSensitivity.INTERNAL: 1,
            DataSensitivity.CONFIDENTIAL: 2,
            DataSensitivity.PII: 3,
            DataSensitivity.SECRET: 4,
        }
        
        max_level = max(hierarchy.get(tag.sensitivity, 0) for tag in self.tags)
        
        for sensitivity, level in hierarchy.items():
            if level == max_level:
                return sensitivity
        
        return DataSensitivity.INTERNAL


__all__ = [
    "TaintSource",
    "DataSensitivity",
    "TaintTag",
    "TaintedData",
]
