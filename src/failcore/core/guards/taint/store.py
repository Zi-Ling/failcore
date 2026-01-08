# failcore/core/guards/taint/store.py
"""
Taint Store - Run-scoped taint state management

Maintains taint tags across steps within a run, enabling data flow tracking.
"""
from typing import Dict, Set, Optional
from .tag import TaintTag
from .context import TaintContext


class TaintStore:
    """
    Run-scoped taint store
    
    Maintains mapping: step_id -> taint tags
    Used by DLPMiddleware to track data flow across tool boundaries.
    """
    
    def __init__(self, taint_context: Optional[TaintContext] = None):
        """
        Initialize taint store
        
        Args:
            taint_context: Optional TaintContext instance (creates new if None)
        """
        self.taint_context = taint_context or TaintContext()
    
    def mark_tainted(self, step_id: str, tag: TaintTag) -> None:
        """Mark step output as tainted"""
        self.taint_context.mark_tainted(step_id, tag)
    
    def is_tainted(self, step_id: str) -> bool:
        """Check if step output is tainted"""
        return self.taint_context.is_tainted(step_id)
    
    def get_tags(self, step_id: str) -> Set[TaintTag]:
        """Get taint tags for step"""
        return self.taint_context.get_tags(step_id)
    
    def detect_tainted_inputs(
        self,
        params: Dict,
        dependencies: Optional[list] = None
    ) -> Set[TaintTag]:
        """
        Detect if tool inputs contain tainted data
        
        Args:
            params: Tool parameters
            dependencies: List of step_ids this tool depends on
        
        Returns:
            Set of taint tags from dependencies
        """
        return self.taint_context.detect_tainted_inputs(params, dependencies)
    
    def is_source_tool(self, tool_name: str) -> bool:
        """Check if tool is a data source"""
        return self.taint_context.is_source_tool(tool_name)
    
    def is_sink_tool(self, tool_name: str) -> bool:
        """Check if tool is a data sink"""
        return self.taint_context.is_sink_tool(tool_name)
    
    def clear(self) -> None:
        """Clear all taint tags (for cleanup)"""
        self.taint_context.clear()
    
    def get_summary(self) -> Dict:
        """Get taint tracking summary"""
        return self.taint_context.get_summary()


__all__ = ["TaintStore"]
