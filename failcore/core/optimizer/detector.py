"""
Tool Call Pattern Detector

Detect patterns in tool call traces for optimization
"""

from typing import Dict, Any, List, Optional
from collections import defaultdict
import hashlib
import json

from .models import PatternType, CallPattern
from .resources import ResourceIdExtractor, ResourceMutationDetector
from .state import WriteBarrierTracker


class PatternDetector:
    """
    Pattern detector for tool call optimization
    
    Analyzes trace to find:
    - Repeated calls (with write barrier awareness)
    - Redundant parameters
    - Sequential operations
    """
    
    def __init__(self):
        # Call history for pattern detection
        self.call_history: List[Dict[str, Any]] = []
        self.call_signatures: Dict[str, List[str]] = defaultdict(list)  # signature -> step_ids
        
        # Resource tracking
        self.resource_extractor = ResourceIdExtractor()
        self.mutation_detector = ResourceMutationDetector()
        self.write_barrier = WriteBarrierTracker()
        
    def record_call(
        self,
        step_id: str,
        tool_name: str,
        params: Dict[str, Any],
        result: Any = None,
    ) -> None:
        """Record a tool call"""
        # Extract resource IDs
        resource_ids = self.resource_extractor.extract(tool_name, params)
        
        # Detect mutations
        mutation_type = self.mutation_detector.detect_mutation(tool_name, params)
        
        # Record in write barrier tracker
        seq = self.write_barrier.record_access(
            resource_ids=resource_ids,
            mutation_type=mutation_type,
            step_id=step_id,
            tool_name=tool_name,
        )
        
        call = {
            "step_id": step_id,
            "tool_name": tool_name,
            "params": params,
            "result": result,
            "signature": self._compute_signature(tool_name, params),
            "resource_ids": resource_ids,
            "mutation_type": mutation_type,
            "seq": seq,
        }
        
        self.call_history.append(call)
        self.call_signatures[call["signature"]].append(step_id)
    
    def analyze(self) -> List[CallPattern]:
        """Analyze recorded calls for patterns"""
        patterns = []
        
        # Detect repeated calls
        patterns.extend(self._detect_repeated_calls())
        
        # Detect redundant parameters
        patterns.extend(self._detect_redundant_params())
        
        # Detect sequential reads
        patterns.extend(self._detect_sequential_reads())
        
        # Detect write-read cycles
        patterns.extend(self._detect_write_read_cycles())
        
        return patterns
    
    def _compute_signature(self, tool_name: str, params: Dict[str, Any]) -> str:
        """Compute signature for call (tool + params)"""
        # Sort params for consistent hashing
        params_str = json.dumps(params, sort_keys=True, default=str)
        signature = f"{tool_name}:{hashlib.md5(params_str.encode()).hexdigest()}"
        return signature
    
    def _detect_repeated_calls(self) -> List[CallPattern]:
        """Detect repeated identical calls (respecting write barriers)"""
        patterns = []
        
        for signature, step_ids in self.call_signatures.items():
            if len(step_ids) <= 1:
                continue
            
            # Get all calls with this signature
            calls = [c for c in self.call_history if c["step_id"] in step_ids]
            
            # Check if these are truly redundant (no writes between them)
            cacheable_groups = self._find_cacheable_groups(calls)
            
            for group in cacheable_groups:
                if len(group) > 1:
                    first_call = group[0]
                    
                    pattern = CallPattern(
                        pattern_type=PatternType.REPEATED_CALL,
                        tool_name=first_call["tool_name"],
                        occurrences=len(group),
                        step_ids=[c["step_id"] for c in group],
                        params_sample=first_call["params"],
                        metadata={
                            "signature": signature,
                            "potential_cache_savings": len(group) - 1,
                            "write_barrier_checked": True,
                        }
                    )
                    patterns.append(pattern)
        
        return patterns
    
    def _find_cacheable_groups(self, calls: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Find groups of calls that can be cached together
        
        Calls in same group have no write barriers between them
        """
        if not calls:
            return []
        
        # Sort by sequence
        sorted_calls = sorted(calls, key=lambda c: c["seq"])
        
        groups = []
        current_group = [sorted_calls[0]]
        
        for i in range(1, len(sorted_calls)):
            prev_call = sorted_calls[i - 1]
            curr_call = sorted_calls[i]
            
            # Check if any resource was modified between calls
            can_cache = True
            for resource_id in curr_call.get("resource_ids", []):
                if not self.write_barrier.can_cache_reuse(
                    resource_id,
                    prev_call["seq"],
                    curr_call["seq"]
                ):
                    can_cache = False
                    break
            
            if can_cache:
                current_group.append(curr_call)
            else:
                # Start new group
                if len(current_group) > 1:
                    groups.append(current_group)
                current_group = [curr_call]
        
        # Add final group
        if len(current_group) > 1:
            groups.append(current_group)
        
        return groups
    
    def _detect_redundant_params(self) -> List[CallPattern]:
        """Detect parameters that don't affect output"""
        patterns = []
        
        # Group by tool name
        by_tool = defaultdict(list)
        for call in self.call_history:
            by_tool[call["tool_name"]].append(call)
        
        # For each tool, check if some params are always the same
        for tool_name, calls in by_tool.items():
            if len(calls) < 2:
                continue
            
            # Find params that are always identical
            all_params = set()
            for call in calls:
                all_params.update(call["params"].keys())
            
            constant_params = []
            for param in all_params:
                values = [call["params"].get(param) for call in calls]
                if len(set(str(v) for v in values)) == 1:
                    constant_params.append(param)
            
            if constant_params and len(constant_params) < len(all_params):
                pattern = CallPattern(
                    pattern_type=PatternType.REDUNDANT_PARAMS,
                    tool_name=tool_name,
                    occurrences=len(calls),
                    step_ids=[c["step_id"] for c in calls],
                    metadata={
                        "redundant_params": constant_params,
                        "total_params": len(all_params),
                    }
                )
                patterns.append(pattern)
        
        return patterns
    
    def _detect_sequential_reads(self) -> List[CallPattern]:
        """Detect sequential read operations"""
        patterns = []
        
        # Look for consecutive read operations
        read_tools = ["read_file", "fetch_url", "db_query"]
        
        consecutive_reads = []
        for i, call in enumerate(self.call_history):
            if call["tool_name"] in read_tools:
                if not consecutive_reads or i == consecutive_reads[-1] + 1:
                    consecutive_reads.append(i)
                else:
                    # End of sequence
                    if len(consecutive_reads) >= 3:
                        calls = [self.call_history[j] for j in consecutive_reads]
                        pattern = CallPattern(
                            pattern_type=PatternType.SEQUENTIAL_READS,
                            tool_name="multiple_reads",
                            occurrences=len(consecutive_reads),
                            step_ids=[c["step_id"] for c in calls],
                            metadata={
                                "tools": [c["tool_name"] for c in calls],
                            }
                        )
                        patterns.append(pattern)
                    consecutive_reads = [i]
        
        return patterns
    
    def _detect_write_read_cycles(self) -> List[CallPattern]:
        """Detect write followed by immediate read (using resource IDs)"""
        patterns = []
        
        for i in range(len(self.call_history) - 1):
            curr = self.call_history[i]
            next_call = self.call_history[i + 1]
            
            # Check if current is a write
            if curr.get("mutation_type") is None:
                continue
            
            # Check if next is a read (no mutation)
            if next_call.get("mutation_type") is not None:
                continue
            
            # Check if they operate on same resource
            curr_resources = set(curr.get("resource_ids", []))
            next_resources = set(next_call.get("resource_ids", []))
            
            common_resources = curr_resources & next_resources
            
            if common_resources:
                for resource_id in common_resources:
                    pattern = CallPattern(
                        pattern_type=PatternType.WRITE_READ_CYCLE,
                        tool_name=f"{curr['tool_name']}->{next_call['tool_name']}",
                        occurrences=1,
                        step_ids=[curr["step_id"], next_call["step_id"]],
                        metadata={
                            "resource_id": resource_id,
                            "write_tool": curr["tool_name"],
                            "read_tool": next_call["tool_name"],
                            "mutation_type": curr["mutation_type"].value if curr.get("mutation_type") else None,
                        }
                    )
                    patterns.append(pattern)
                    break  # One pattern per write-read pair
        
        return patterns
    
    def clear(self) -> None:
        """Clear recorded calls"""
        self.call_history.clear()
        self.call_signatures.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detection statistics"""
        return {
            "total_calls": len(self.call_history),
            "unique_signatures": len(self.call_signatures),
            "tools_used": len(set(c["tool_name"] for c in self.call_history)),
        }


__all__ = ["PatternDetector"]
