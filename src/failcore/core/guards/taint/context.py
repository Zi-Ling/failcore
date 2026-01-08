"""
Taint Tracking - Context

Track tainted data across tool calls
"""

from typing import Dict, Set, Any, List
from .tag import TaintTag, TaintSource, DataSensitivity


class TaintContext:
    """
    Track tainted data in execution context
    
    Maintains mapping: step_id -> taint tags
    Propagates taint across tool boundaries
    """
    
    def __init__(self):
        # step_id -> set of taint tags
        self._taint_map: Dict[str, Set[TaintTag]] = {}
        
        # Tool classifications
        self._source_tools: Set[str] = {
            "read_file", "read_dir", "db_query", "db_fetch",
            "api_call", "http_get", "fetch_url",
            "get_env", "read_secret", "read_config",
        }
        
        self._sink_tools: Set[str] = {
            "write_file", "db_insert", "db_update",
            "api_post", "http_post", "send_email",
            "upload_file", "publish_message", "log_external",
        }
    
    def mark_tainted(
        self,
        step_id: str,
        tag: TaintTag
    ) -> None:
        """Mark step output as tainted"""
        if step_id not in self._taint_map:
            self._taint_map[step_id] = set()
        
        self._taint_map[step_id].add(tag)
    
    def is_tainted(self, step_id: str) -> bool:
        """Check if step output is tainted"""
        return step_id in self._taint_map and len(self._taint_map[step_id]) > 0
    
    def get_tags(self, step_id: str) -> Set[TaintTag]:
        """Get taint tags for step"""
        return self._taint_map.get(step_id, set())
    
    def detect_tainted_inputs(
        self,
        params: Dict[str, Any],
        dependencies: List[str] = None
    ) -> Set[TaintTag]:
        """
        Detect if tool inputs contain tainted data
        
        Args:
            params: Tool parameters
            dependencies: List of step_ids this tool depends on
        
        Returns:
            Set of taint tags from dependencies
        """
        all_tags = set()
        
        # Check dependencies
        if dependencies:
            for dep_step_id in dependencies:
                if self.is_tainted(dep_step_id):
                    all_tags.update(self.get_tags(dep_step_id))
        
        # Check if params reference tainted steps
        # (Simple heuristic: look for step_id patterns in params)
        for value in params.values():
            if isinstance(value, str):
                for step_id in self._taint_map.keys():
                    if step_id in value:
                        all_tags.update(self.get_tags(step_id))
        
        return all_tags
    
    def is_source_tool(self, tool_name: str) -> bool:
        """Check if tool is a data source (produces tainted data)"""
        # Exact match
        if tool_name in self._source_tools:
            return True
        
        # Pattern match
        source_patterns = ["read", "fetch", "get", "query", "load", "retrieve"]
        return any(pattern in tool_name.lower() for pattern in source_patterns)
    
    def is_sink_tool(self, tool_name: str) -> bool:
        """Check if tool is a data sink (consumes data for external output)"""
        # Exact match
        if tool_name in self._sink_tools:
            return True
        
        # Pattern match
        sink_patterns = ["write", "send", "post", "upload", "publish", "export", "log"]
        return any(pattern in tool_name.lower() for pattern in sink_patterns)
    
    def register_source_tool(self, tool_name: str) -> None:
        """Register custom source tool"""
        self._source_tools.add(tool_name)
    
    def register_sink_tool(self, tool_name: str) -> None:
        """Register custom sink tool"""
        self._sink_tools.add(tool_name)
    
    def clear(self) -> None:
        """Clear all taint tags (for cleanup)"""
        self._taint_map.clear()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get taint tracking summary"""
        total_tainted_steps = len(self._taint_map)
        
        sensitivity_counts = {}
        source_counts = {}
        
        for tags in self._taint_map.values():
            for tag in tags:
                sensitivity_counts[tag.sensitivity.value] = sensitivity_counts.get(tag.sensitivity.value, 0) + 1
                source_counts[tag.source.value] = source_counts.get(tag.source.value, 0) + 1
        
        return {
            "tainted_steps": total_tainted_steps,
            "sensitivity_distribution": sensitivity_counts,
            "source_distribution": source_counts,
        }


__all__ = ["TaintContext"]
