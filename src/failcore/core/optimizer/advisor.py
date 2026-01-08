"""
Optimization Advisor

Generate actionable optimization suggestions based on trace analysis
"""

from typing import Dict, Any, List, Optional

from .models import (
    PatternType,
    CallPattern,
    CacheOpportunity,
    SuggestionType,
    RedundancyStrategy,
    Suggestion,
)
from .detector import PatternDetector
from .cache import CacheAnalyzer


class OptimizationAdvisor:
    """
    Generate optimization advice from trace analysis
    
    Features:
    - Actionable suggestions
    - Verifiable recommendations
    - NO automatic changes
    - Clear impact estimates
    """
    
    def __init__(
        self,
        pattern_detector: PatternDetector = None,
        cache_analyzer: CacheAnalyzer = None,
        min_confidence: float = 0.7,
    ):
        """
        Args:
            pattern_detector: Pattern detector
            cache_analyzer: Cache analyzer
            min_confidence: Minimum confidence for suggestions
        """
        self.pattern_detector = pattern_detector or PatternDetector()
        self.cache_analyzer = cache_analyzer or CacheAnalyzer()
        self.min_confidence = min_confidence
    
    def analyze_trace(
        self,
        calls: List[Dict[str, Any]]
    ) -> List[Suggestion]:
        """
        Analyze trace and generate suggestions
        
        Args:
            calls: List of call records
        
        Returns:
            List of optimization suggestions
        """
        suggestions = []
        
        # Record calls for pattern detection
        for call in calls:
            self.pattern_detector.record_call(
                step_id=call.get("step_id", ""),
                tool_name=call.get("tool_name", ""),
                params=call.get("params", {}),
                result=call.get("result"),
            )
        
        # Detect patterns
        patterns = self.pattern_detector.analyze()
        
        # Generate suggestions from patterns
        for pattern in patterns:
            suggestion = self._pattern_to_suggestion(pattern)
            if suggestion and suggestion.confidence >= self.min_confidence:
                suggestions.append(suggestion)
        
        # Analyze caching opportunities
        cache_opportunities = self.cache_analyzer.analyze_calls(calls)
        
        # Generate caching suggestions
        for opportunity in cache_opportunities:
            suggestion = self._cache_to_suggestion(opportunity)
            if suggestion and suggestion.confidence >= self.min_confidence:
                suggestions.append(suggestion)
        
        # Sort by impact (prioritize high-impact suggestions)
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        
        return suggestions
    
    def _pattern_to_suggestion(self, pattern: CallPattern) -> Optional[Suggestion]:
        """Convert pattern to suggestion (unified REDUNDANCY type)"""
        if pattern.pattern_type == PatternType.REPEATED_CALL:
            return Suggestion(
                suggestion_type=SuggestionType.REDUNDANCY,
                strategy=RedundancyStrategy.DEDUPE.value,
                title=f"Deduplicate {pattern.tool_name} calls",
                description=pattern.get_description(),
                impact=f"Save {pattern.occurrences - 1} redundant calls",
                confidence=0.95,
                action=f"Cache result of {pattern.tool_name} or refactor to call once",
                affected_steps=pattern.step_ids,
                metadata={
                    "pattern": pattern.to_dict(),
                    "write_barrier_checked": pattern.metadata.get("write_barrier_checked", False),
                }
            )
        
        elif pattern.pattern_type == PatternType.REDUNDANT_PARAMS:
            redundant = pattern.metadata.get("redundant_params", [])
            return Suggestion(
                suggestion_type=SuggestionType.REDUNDANCY,
                strategy=RedundancyStrategy.SIMPLIFY.value,
                title=f"Remove redundant parameters from {pattern.tool_name}",
                description=pattern.get_description(),
                impact=f"Simplify {pattern.occurrences} calls",
                confidence=0.85,
                action=f"Remove parameters: {', '.join(redundant)}",
                affected_steps=pattern.step_ids,
                metadata={
                    "redundant_params": redundant,
                }
            )
        
        elif pattern.pattern_type == PatternType.SEQUENTIAL_READS:
            return Suggestion(
                suggestion_type=SuggestionType.REDUNDANCY,
                strategy=RedundancyStrategy.COALESCE.value,
                title="Batch sequential read operations",
                description=pattern.get_description(),
                impact=f"Reduce {pattern.occurrences} calls to 1 batch call",
                confidence=0.80,
                action="Use batch read API or parallel execution",
                affected_steps=pattern.step_ids,
                metadata={
                    "tools": pattern.metadata.get("tools", []),
                }
            )
        
        elif pattern.pattern_type == PatternType.WRITE_READ_CYCLE:
            return Suggestion(
                suggestion_type=SuggestionType.REDUNDANCY,
                strategy=RedundancyStrategy.REORDER.value,
                title="Eliminate write-read cycle",
                description=pattern.get_description(),
                impact="Save 1 read operation",
                confidence=0.90,
                action="Reuse written data instead of re-reading",
                affected_steps=pattern.step_ids,
                metadata={
                    "resource_id": pattern.metadata.get("resource_id"),
                }
            )
        
        return None
    
    def _cache_to_suggestion(self, opportunity: CacheOpportunity) -> Optional[Suggestion]:
        """Convert cache opportunity to suggestion"""
        if opportunity.call_count < 2:
            return None
        
        # Adjust confidence and action based on determinism (three-state)
        determinism = opportunity.metadata.get("determinism", "unknown")
        
        if determinism == "deterministic":
            confidence = 0.95
            action = f"Enable caching for {opportunity.tool_name}"
        elif determinism == "unknown":
            confidence = 0.70
            action = f"Consider marking {opportunity.tool_name} as deterministic, then enable caching"
        else:  # non_deterministic - shouldn't reach here but handle gracefully
            confidence = 0.40
            action = f"⚠️  {opportunity.tool_name} is non-deterministic - caching unsafe"
        
        return Suggestion(
            suggestion_type=SuggestionType.REDUNDANCY,
            strategy=RedundancyStrategy.CACHE.value,
            title=f"Cache {opportunity.tool_name} results",
            description=opportunity.get_description(),
            impact=f"Save {opportunity.call_count - 1} calls, ~{opportunity.estimated_savings:.2f}s",
            confidence=confidence,
            action=action,
            affected_steps=opportunity.step_ids,
            metadata={
                "cache_key": opportunity.cache_key,
                "estimated_savings": opportunity.estimated_savings,
                "determinism": determinism,
                "write_barrier_safe": opportunity.metadata.get("write_barrier_safe", False),
            }
        )
    
    def generate_report(
        self,
        calls: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate comprehensive optimization report
        
        Args:
            calls: List of call records
        
        Returns:
            Optimization report with suggestions and statistics
        """
        # Analyze
        suggestions = self.analyze_trace(calls)
        
        # Get cache simulation
        cache_stats = self.cache_analyzer.simulate_cache(calls)
        
        # Get pattern stats
        pattern_stats = self.pattern_detector.get_stats()
        
        # Categorize suggestions by strategy
        by_strategy = {}
        for suggestion in suggestions:
            strategy = suggestion.strategy
            if strategy not in by_strategy:
                by_strategy[strategy] = []
            by_strategy[strategy].append(suggestion)
        
        # Calculate total impact
        total_calls_saved = sum(
            s.metadata.get("pattern", {}).get("occurrences", 1) - 1
            for s in suggestions
            if s.strategy in ["dedupe", "cache"]
        )
        
        return {
            "total_calls": len(calls),
            "suggestions": [s.to_dict() for s in suggestions],
            "suggestion_count": len(suggestions),
            "by_strategy": {k: len(v) for k, v in by_strategy.items()},
            "cache_stats": cache_stats,
            "pattern_stats": pattern_stats,
            "estimated_impact": {
                "calls_saved": total_calls_saved,
                "time_saved_sec": cache_stats.get("estimated_savings_sec", 0),
            }
        }
    
    def get_top_suggestions(
        self,
        calls: List[Dict[str, Any]],
        limit: int = 5
    ) -> List[Suggestion]:
        """Get top N suggestions by confidence"""
        suggestions = self.analyze_trace(calls)
        return suggestions[:limit]


__all__ = ["OptimizationAdvisor"]
