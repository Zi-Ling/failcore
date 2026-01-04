"""
Resource State Tracking

Track resource versions and write barriers for cache correctness
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Set
from .resources import MutationType


@dataclass
class ResourceState:
    """
    Resource state tracking
    
    Tracks:
    - Last write sequence number
    - Version counter
    - Mutation history
    """
    resource_id: str
    version: int = 0  # Incremented on each mutation
    last_write_seq: int = -1  # Sequence number of last write
    last_mutation_type: Optional[MutationType] = None
    mutation_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def record_mutation(
        self,
        seq: int,
        mutation_type: MutationType,
        step_id: str,
        tool_name: str,
    ) -> None:
        """Record a mutation to this resource"""
        self.version += 1
        self.last_write_seq = seq
        self.last_mutation_type = mutation_type
        
        self.mutation_history.append({
            "seq": seq,
            "step_id": step_id,
            "tool_name": tool_name,
            "mutation_type": mutation_type.value,
            "version": self.version,
        })
    
    def get_version_at_seq(self, seq: int) -> int:
        """Get resource version at given sequence number"""
        # Count mutations before this sequence
        mutations_before = sum(
            1 for m in self.mutation_history if m["seq"] < seq
        )
        return mutations_before
    
    def was_mutated_between(self, seq_start: int, seq_end: int) -> bool:
        """Check if resource was mutated between two sequence numbers"""
        for mutation in self.mutation_history:
            if seq_start < mutation["seq"] <= seq_end:
                return True
        return False


class WriteBarrierTracker:
    """
    Track write barriers for correct cache invalidation
    
    Key insight: Cache is only valid if resource wasn't modified
    between cache write and cache read.
    
    Example:
        seq=1: read(file.txt) -> v1
        seq=2: write(file.txt) -> v2  # BARRIER
        seq=3: read(file.txt) -> should NOT use cache from seq=1
    """
    
    def __init__(self):
        # resource_id -> ResourceState
        self.resource_states: Dict[str, ResourceState] = {}
        
        # Global sequence counter
        self.seq_counter = 0
        
        # Cache validity tracking
        # (resource_id, seq) -> is_valid
        self.cache_validity: Dict[tuple, bool] = {}
    
    def record_access(
        self,
        resource_ids: List[str],
        mutation_type: Optional[MutationType],
        step_id: str,
        tool_name: str,
    ) -> int:
        """
        Record resource access
        
        Args:
            resource_ids: List of accessed resources
            mutation_type: Type of mutation (None for read-only)
            step_id: Step ID
            tool_name: Tool name
        
        Returns:
            Sequence number for this access
        """
        self.seq_counter += 1
        seq = self.seq_counter
        
        # Record mutations
        if mutation_type is not None:
            for resource_id in resource_ids:
                self._record_mutation(resource_id, seq, mutation_type, step_id, tool_name)
        
        return seq
    
    def _record_mutation(
        self,
        resource_id: str,
        seq: int,
        mutation_type: MutationType,
        step_id: str,
        tool_name: str,
    ) -> None:
        """Record mutation to resource"""
        if resource_id not in self.resource_states:
            self.resource_states[resource_id] = ResourceState(resource_id=resource_id)
        
        state = self.resource_states[resource_id]
        state.record_mutation(seq, mutation_type, step_id, tool_name)
        
        # Invalidate all cache entries for this resource
        self._invalidate_cache(resource_id)
    
    def _invalidate_cache(self, resource_id: str) -> None:
        """Invalidate cache entries for resource"""
        # Mark all cache entries for this resource as invalid
        keys_to_invalidate = [
            key for key in self.cache_validity.keys()
            if key[0] == resource_id
        ]
        for key in keys_to_invalidate:
            self.cache_validity[key] = False
    
    def can_cache_reuse(
        self,
        resource_id: str,
        cached_seq: int,
        current_seq: int,
    ) -> bool:
        """
        Check if cached result can be reused
        
        Args:
            resource_id: Resource ID
            cached_seq: Sequence when cached
            current_seq: Current sequence
        
        Returns:
            True if cache is valid (no mutations between)
        """
        if resource_id not in self.resource_states:
            # Resource never mutated, cache is valid
            return True
        
        state = self.resource_states[resource_id]
        
        # Check if resource was mutated between cached and current
        return not state.was_mutated_between(cached_seq, current_seq)
    
    def get_resource_version(
        self,
        resource_id: str,
        seq: Optional[int] = None
    ) -> int:
        """
        Get resource version
        
        Args:
            resource_id: Resource ID
            seq: Sequence number (None = current)
        
        Returns:
            Version number
        """
        if resource_id not in self.resource_states:
            return 0
        
        state = self.resource_states[resource_id]
        
        if seq is None:
            return state.version
        else:
            return state.get_version_at_seq(seq)
    
    def get_mutations_for_resource(
        self,
        resource_id: str
    ) -> List[Dict[str, Any]]:
        """Get mutation history for resource"""
        if resource_id not in self.resource_states:
            return []
        
        return self.resource_states[resource_id].mutation_history.copy()
    
    def get_mutated_resources(self) -> Set[str]:
        """Get all resources that have been mutated"""
        return set(self.resource_states.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tracking statistics"""
        return {
            "total_sequences": self.seq_counter,
            "tracked_resources": len(self.resource_states),
            "total_mutations": sum(
                len(state.mutation_history)
                for state in self.resource_states.values()
            ),
        }
    
    def clear(self) -> None:
        """Clear all state"""
        self.resource_states.clear()
        self.cache_validity.clear()
        self.seq_counter = 0


__all__ = [
    "ResourceState",
    "WriteBarrierTracker",
]
