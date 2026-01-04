"""
Cache Analyzer

Analyze tool calls for caching opportunities (with write barrier awareness)
"""

from typing import Dict, Any, List
import hashlib
import json

from .models import CacheOpportunity
from .resources import ResourceIdExtractor, ResourceMutationDetector
from .state import WriteBarrierTracker


class CacheAnalyzer:
    """
    Analyze tool calls for caching opportunities
    
    Identifies:
    - Repeated identical calls (deterministic)
    - Read-heavy operations
    - Expensive operations called multiple times
    
    WITH CORRECTNESS:
    - Respects write barriers
    - Checks tool determinism
    - Only suggests safe caching
    """
    
    def __init__(
        self,
        min_calls_for_cache: int = 2,
        cacheable_tools: List[str] = None,
        tool_determinism: Dict[str, str] = None,
    ):
        """
        Args:
            min_calls_for_cache: Minimum calls to suggest caching
            cacheable_tools: List of cacheable tool names (None = auto-detect)
            tool_determinism: Map of tool_name -> determinism ("deterministic"/"non_deterministic"/"unknown")
        """
        self.min_calls_for_cache = min_calls_for_cache
        self.cacheable_tools = cacheable_tools or self._default_cacheable_tools()
        self.tool_determinism = tool_determinism or {}  # tool_name -> determinism string
        
        # Resource tracking
        self.resource_extractor = ResourceIdExtractor()
        self.mutation_detector = ResourceMutationDetector()
        self.write_barrier = WriteBarrierTracker()
        
        # Cache hit simulation
        self.call_cache: Dict[str, List[Dict[str, Any]]] = {}
    
    def _default_cacheable_tools(self) -> List[str]:
        """Default list of cacheable tools"""
        return [
            # File operations (deterministic reads)
            "read_file",
            "list_dir",
            "stat_file",
            
            # Database queries (read-only)
            "db_query",
            "db_fetch",
            "db_count",
            
            # API calls (GET methods, deterministic)
            "http_get",
            "fetch_url",
            "api_get",
            
            # Computation (pure functions)
            "calculate",
            "transform",
            "parse",
        ]
    
    def analyze_calls(
        self,
        calls: List[Dict[str, Any]]
    ) -> List[CacheOpportunity]:
        """
        Analyze tool calls for caching opportunities (with correctness checks)
        
        Args:
            calls: List of call records with {tool_name, params, step_id, result}
        
        Returns:
            List of cache opportunities
        """
        opportunities = []
        
        # First pass: record all calls for write barrier tracking
        seq_map = {}  # step_id -> seq
        for call in calls:
            tool_name = call.get("tool_name", "")
            params = call.get("params", {})
            step_id = call.get("step_id", "")
            
            # Extract resources
            resource_ids = self.resource_extractor.extract(tool_name, params)
            mutation_type = self.mutation_detector.detect_mutation(tool_name, params)
            
            # Record in write barrier
            seq = self.write_barrier.record_access(
                resource_ids=resource_ids,
                mutation_type=mutation_type,
                step_id=step_id,
                tool_name=tool_name,
            )
            seq_map[step_id] = seq
            
            # Enrich call with tracking info
            call["resource_ids"] = resource_ids
            call["mutation_type"] = mutation_type
            call["seq"] = seq
        
        # Second pass: group calls by cache key
        call_groups: Dict[str, List[Dict[str, Any]]] = {}
        
        for call in calls:
            tool_name = call.get("tool_name", "")
            params = call.get("params", {})
            
            # Skip non-cacheable tools
            if not self._is_cacheable_with_checks(tool_name, params):
                continue
            
            # Compute cache key
            cache_key = self._compute_cache_key(tool_name, params)
            
            if cache_key not in call_groups:
                call_groups[cache_key] = []
            call_groups[cache_key].append(call)
        
        # Third pass: find TRUE opportunities (respecting write barriers)
        for cache_key, group in call_groups.items():
            if len(group) < self.min_calls_for_cache:
                continue
            
            # Sort by sequence
            group_sorted = sorted(group, key=lambda c: c.get("seq", 0))
            
            # Find cacheable subgroups (no writes between)
            cacheable_groups = self._find_cacheable_subgroups(group_sorted)
            
            for subgroup in cacheable_groups:
                if len(subgroup) >= self.min_calls_for_cache:
                    first_call = subgroup[0]
                    
                    opportunity = CacheOpportunity(
                        tool_name=first_call["tool_name"],
                        params=first_call["params"],
                        call_count=len(subgroup),
                        step_ids=[c["step_id"] for c in subgroup],
                        estimated_savings=self._estimate_savings(subgroup),
                        cache_key=cache_key,
                        metadata={
                            "first_call": first_call["step_id"],
                            "cacheable": True,
                            "write_barrier_safe": True,
                            "determinism": self._get_determinism(first_call["tool_name"]),
                        }
                    )
                    opportunities.append(opportunity)
        
        return opportunities
    
    def _find_cacheable_subgroups(
        self,
        calls: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Find subgroups where caching is safe (no write barriers)"""
        if not calls:
            return []
        
        subgroups = []
        current_group = [calls[0]]
        
        for i in range(1, len(calls)):
            prev_call = calls[i - 1]
            curr_call = calls[i]
            
            # Check write barrier for all resources
            can_cache = True
            for resource_id in curr_call.get("resource_ids", []):
                if not self.write_barrier.can_cache_reuse(
                    resource_id,
                    prev_call.get("seq", 0),
                    curr_call.get("seq", 0)
                ):
                    can_cache = False
                    break
            
            if can_cache:
                current_group.append(curr_call)
            else:
                # Save current group if big enough
                if len(current_group) >= self.min_calls_for_cache:
                    subgroups.append(current_group)
                current_group = [curr_call]
        
        # Add final group
        if len(current_group) >= self.min_calls_for_cache:
            subgroups.append(current_group)
        
        return subgroups
    
    def _is_cacheable(self, tool_name: str) -> bool:
        """Check if tool is cacheable (basic check)"""
        # Check explicit list
        if tool_name in self.cacheable_tools:
            return True
        
        # Heuristic: read operations are usually cacheable
        read_keywords = ["read", "get", "fetch", "list", "query", "search"]
        return any(keyword in tool_name.lower() for keyword in read_keywords)
    
    def _is_cacheable_with_checks(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> bool:
        """Check if tool is cacheable (with all correctness checks)"""
        # Must be read-only
        if self.mutation_detector.is_mutating(tool_name, params):
            return False
        
        # Must be cacheable by name
        if not self._is_cacheable(tool_name):
            return False
        
        # Check determinism (three-state)
        determinism = self.tool_determinism.get(tool_name, "unknown")
        if determinism == "non_deterministic":
            # Explicitly non-deterministic - don't cache
            return False
        
        # "deterministic" or "unknown" - allow caching (with adjusted confidence)
        return True
    
    def _get_determinism(self, tool_name: str) -> str:
        """Get determinism classification for tool"""
        return self.tool_determinism.get(tool_name, "unknown")
    
    def _compute_cache_key(self, tool_name: str, params: Dict[str, Any]) -> str:
        """Compute cache key for tool call"""
        # Sort params for consistent hashing
        params_str = json.dumps(params, sort_keys=True, default=str)
        key_data = f"{tool_name}:{params_str}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    def _estimate_savings(self, calls: List[Dict[str, Any]]) -> float:
        """Estimate time/cost savings from caching"""
        # Simple heuristic: assume each cached call saves 100ms
        # In production, use actual timing data from trace
        savings_per_call = 0.1  # 100ms
        cache_hits = len(calls) - 1  # First call is cache miss
        return cache_hits * savings_per_call
    
    def simulate_cache(
        self,
        calls: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Simulate cache behavior
        
        Returns statistics about cache hits/misses
        """
        hits = 0
        misses = 0
        cache: Dict[str, Any] = {}
        
        for call in calls:
            tool_name = call.get("tool_name", "")
            params = call.get("params", {})
            
            if not self._is_cacheable(tool_name):
                continue
            
            cache_key = self._compute_cache_key(tool_name, params)
            
            if cache_key in cache:
                hits += 1
            else:
                misses += 1
                cache[cache_key] = call.get("result")
        
        total = hits + misses
        hit_rate = hits / total if total > 0 else 0.0
        
        return {
            "cache_hits": hits,
            "cache_misses": misses,
            "total_cacheable_calls": total,
            "hit_rate": hit_rate,
            "estimated_savings_sec": hits * 0.1,  # 100ms per hit
        }


__all__ = ["CacheAnalyzer"]
