"""
Taint Flow Tracking

Minimal propagation model for cross-tool boundary taint tracking.
Tracks taint flow edges: tool A output -> tool B input.
"""

from __future__ import annotations

from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from .tag import TaintTag, TaintSource, DataSensitivity


@dataclass
class TaintEdge:
    """
    Taint flow edge: source step -> sink step
    
    Represents data flow from one tool to another.
    """
    source_step_id: str
    source_tool: str
    sink_step_id: str
    sink_tool: str
    field_path: Optional[str] = None  # JSON path where taint flows (e.g., "user.email")
    tags: Set[TaintTag] = field(default_factory=set)
    
    def to_dict(self) -> Dict:
        """Convert to dict for serialization"""
        return {
            "source_step_id": self.source_step_id,
            "source_tool": self.source_tool,
            "sink_step_id": self.sink_step_id,
            "sink_tool": self.sink_tool,
            "field_path": self.field_path,
            "tags": [tag.to_dict() for tag in self.tags],
        }


class TaintFlowTracker:
    """
    Track taint flow across tool boundaries
    
    Maintains:
    - step_id -> taint tags (what data is tainted)
    - taint edges (source -> sink flow)
    - flow chains (multi-hop flows)
    """
    
    def __init__(self):
        """Initialize taint flow tracker"""
        # step_id -> set of taint tags
        self._taint_map: Dict[str, Set[TaintTag]] = {}
        
        # List of taint edges (source -> sink)
        self._edges: List[TaintEdge] = []
        
        # step_id -> list of incoming edges
        self._incoming_edges: Dict[str, List[TaintEdge]] = {}
        
        # step_id -> list of outgoing edges
        self._outgoing_edges: Dict[str, List[TaintEdge]] = {}
    
    def mark_source(
        self,
        step_id: str,
        tool_name: str,
        tag: TaintTag,
    ) -> None:
        """
        Mark step output as tainted source
        
        Args:
            step_id: Step ID
            tool_name: Tool name
            tag: Taint tag
        """
        if step_id not in self._taint_map:
            self._taint_map[step_id] = set()
        
        self._taint_map[step_id].add(tag)
    
    def track_flow(
        self,
        source_step_id: str,
        source_tool: str,
        sink_step_id: str,
        sink_tool: str,
        field_path: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[TaintEdge]:
        """
        Track taint flow from source to sink
        
        Auto-detects field_path if not provided using heuristics.
        
        Args:
            source_step_id: Source step ID
            source_tool: Source tool name
            sink_step_id: Sink step ID
            sink_tool: Sink tool name
            field_path: Optional JSON path where taint flows
            params: Optional sink parameters for auto-detection
            
        Returns:
            TaintEdge if flow detected, None otherwise
        """
        # Get taint tags from source
        source_tags = self._taint_map.get(source_step_id, set())
        
        if not source_tags:
            return None  # No taint to propagate
        
        # Auto-detect field_path if not provided
        binding_confidence = "high"  # Default: explicit field_path
        if not field_path and params:
            field_path = self._auto_detect_field_path(source_step_id, params)
            if field_path:
                binding_confidence = "medium"  # Auto-detected has lower confidence
            else:
                binding_confidence = "low"
        
        # Create edge
        edge = TaintEdge(
            source_step_id=source_step_id,
            source_tool=source_tool,
            sink_step_id=sink_step_id,
            sink_tool=sink_tool,
            field_path=field_path,
            tags=source_tags.copy(),
        )
        
        # Add binding confidence to edge metadata (if edge supports it)
        if hasattr(edge, "metadata"):
            if edge.metadata is None:
                edge.metadata = {}
            edge.metadata["binding_confidence"] = binding_confidence
        
        # Add to edges
        self._edges.append(edge)
        
        # Update incoming/outgoing maps
        if sink_step_id not in self._incoming_edges:
            self._incoming_edges[sink_step_id] = []
        self._incoming_edges[sink_step_id].append(edge)
        
        if source_step_id not in self._outgoing_edges:
            self._outgoing_edges[source_step_id] = []
        self._outgoing_edges[source_step_id].append(edge)
        
        # Propagate taint to sink
        if sink_step_id not in self._taint_map:
            self._taint_map[sink_step_id] = set()
        self._taint_map[sink_step_id].update(source_tags)
        
        return edge
    
    def _auto_detect_field_path(
        self,
        source_step_id: str,
        params: Dict[str, Any],
    ) -> Optional[str]:
        """
        Auto-detect field path where taint flows
        
        Uses heuristics:
        - Fields containing step_id
        - Common field names (input, content, data, value, text)
        - Nested structures
        
        Returns:
            Detected field path or None
        """
        # Check for step_id references
        for key, value in params.items():
            if isinstance(value, str) and source_step_id in value:
                return key
        
        # Check common field names
        common_fields = ["input", "content", "data", "value", "text", "body", "message"]
        for field in common_fields:
            if field in params:
                return field
        
        # Check nested structures
        for key, value in params.items():
            if isinstance(value, dict):
                # Check nested dict for step_id
                for nested_key, nested_value in value.items():
                    if isinstance(nested_value, str) and source_step_id in nested_value:
                        return f"{key}.{nested_key}"
        
        return None
    
    def get_flow_chain(
        self,
        step_id: str,
        max_depth: int = 10,
    ) -> List[TaintEdge]:
        """
        Get flow chain leading to this step
        
        Args:
            step_id: Step ID
            max_depth: Maximum chain depth
            
        Returns:
            List of edges in flow chain (ordered from source to sink)
        """
        chain = []
        visited = set()
        current_step = step_id
        depth = 0
        
        while current_step and depth < max_depth:
            if current_step in visited:
                break  # Cycle detected
            
            visited.add(current_step)
            
            # Get incoming edges
            incoming = self._incoming_edges.get(current_step, [])
            if not incoming:
                break  # No more sources
            
            # Use first incoming edge (could extend to handle multiple)
            edge = incoming[0]
            chain.insert(0, edge)
            current_step = edge.source_step_id
            depth += 1
        
        return chain
    
    def get_taint_sources(
        self,
        step_id: str,
    ) -> List[Tuple[str, str, Set[TaintTag]]]:
        """
        Get all taint sources for a step
        
        Args:
            step_id: Step ID
            
        Returns:
            List of (source_step_id, source_tool, tags) tuples
        """
        sources = []
        
        # Get direct tags
        tags = self._taint_map.get(step_id, set())
        if tags:
            # Find original sources
            for tag in tags:
                sources.append((tag.source_step_id, tag.source_tool, {tag}))
        
        # Get from flow chain
        chain = self.get_flow_chain(step_id)
        for edge in chain:
            sources.append((edge.source_step_id, edge.source_tool, edge.tags))
        
        return sources
    
    def get_evidence(
        self,
        step_id: str,
    ) -> Dict:
        """
        Get evidence for taint flow to step
        
        Args:
            step_id: Step ID
            
        Returns:
            Evidence dict with flow chain, sources, etc.
        """
        tags = self._taint_map.get(step_id, set())
        chain = self.get_flow_chain(step_id)
        sources = self.get_taint_sources(step_id)
        
        # Determine max sensitivity
        max_sensitivity = DataSensitivity.INTERNAL
        if tags:
            hierarchy = {
                DataSensitivity.PUBLIC: 0,
                DataSensitivity.INTERNAL: 1,
                DataSensitivity.CONFIDENTIAL: 2,
                DataSensitivity.PII: 3,
                DataSensitivity.SECRET: 4,
            }
            max_level = max(hierarchy.get(tag.sensitivity, 0) for tag in tags)
            for sensitivity, level in hierarchy.items():
                if level == max_level:
                    max_sensitivity = sensitivity
                    break
        
        return {
            "step_id": step_id,
            "taint_tags": [tag.to_dict() for tag in tags],
            "taint_count": len(tags),
            "max_sensitivity": max_sensitivity.value,
            "flow_chain": [edge.to_dict() for edge in chain],
            "source_steps": [
                {
                    "step_id": src_step_id,
                    "tool": src_tool,
                    "tags": [tag.to_dict() for tag in src_tags],
                }
                for src_step_id, src_tool, src_tags in sources
            ],
            "flow_depth": len(chain),
        }
    
    def clear(self) -> None:
        """Clear all taint flow data"""
        self._taint_map.clear()
        self._edges.clear()
        self._incoming_edges.clear()
        self._outgoing_edges.clear()


__all__ = [
    "TaintEdge",
    "TaintFlowTracker",
]
