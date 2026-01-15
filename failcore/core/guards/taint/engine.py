# failcore/core/guards/taint/engine.py
"""
Taint Engine

Real and NoOp implementations of taint tracking engine.
"""

from typing import Any, Dict
from .types import TaintResult, TaintTag, TaintSource, DataSensitivity


class TaintEngine:
    """
    Taint tracking engine interface
    
    Both RealTaintEngine and NoOpTaintEngine implement this interface.
    """
    
    def track(self, source: str, data: Any) -> None:
        """
        Track taint from source
        
        Args:
            source: Source tool name
            data: Data to track
        """
        raise NotImplementedError
    
    def check_sink(self, sink: str, data: Any) -> TaintResult:
        """
        Check if data flowing to sink is tainted
        
        Args:
            sink: Sink tool name
            data: Data to check
        
        Returns:
            TaintResult with taint information
        """
        raise NotImplementedError


class RealTaintEngine(TaintEngine):
    """
    Real Taint engine implementation
    
    Tracks data flow and checks for sensitive data leakage.
    """
    
    def __init__(
        self,
        propagation_mode: str = "whole",
        max_path_depth: int = 3,
        max_paths_per_step: int = 100,
    ):
        """
        Initialize real Taint engine
        
        Args:
            propagation_mode: Propagation mode (whole/paths)
            max_path_depth: Maximum depth for path-level tracking
            max_paths_per_step: Maximum paths to track per step
        """
        self.propagation_mode = propagation_mode
        self.max_path_depth = max_path_depth
        self.max_paths_per_step = max_paths_per_step
        self._taint_store: Dict[str, TaintTag] = {}  # Simplified store
    
    def track(self, source: str, data: Any) -> None:
        """Track taint from source (simplified implementation)"""
        # Map source to taint source type
        source_map = {
            "read_file": TaintSource.FILE,
            "db_query": TaintSource.DATABASE,
            "api_call": TaintSource.API,
        }
        
        taint_source = source_map.get(source, TaintSource.USER_INPUT)
        sensitivity = DataSensitivity.INTERNAL  # Default
        
        # Store taint tag (simplified - real implementation would track data flow)
        data_id = str(id(data))
        self._taint_store[data_id] = TaintTag(
            source=taint_source,
            sensitivity=sensitivity,
            confidence=0.8,
        )
    
    def check_sink(self, sink: str, data: Any) -> TaintResult:
        """Check if data flowing to sink is tainted"""
        data_id = str(id(data))
        tag = self._taint_store.get(data_id)
        
        if tag:
            return TaintResult(
                tainted=True,
                sources=[tag],
                reason="ok",
                evidence={
                    "sink": sink,
                    "propagation_mode": self.propagation_mode,
                },
            )
        
        return TaintResult(
            tainted=False,
            sources=[],
            reason="ok",
            evidence={"sink": sink},
        )


class NoOpTaintEngine(TaintEngine):
    """
    NoOp Taint engine when module is disabled
    
    Returns no taint with reason="disabled" for observability.
    """
    
    def track(self, source: str, data: Any) -> None:
        """NoOp track - does nothing"""
        pass
    
    def check_sink(self, sink: str, data: Any) -> TaintResult:
        """NoOp check - returns no taint"""
        return TaintResult(
            tainted=False,
            sources=[],
            reason="disabled",
            evidence={
                "status": "disabled",
            },
        )
    
    def __repr__(self) -> str:
        return "NoOpTaintEngine(disabled)"


__all__ = [
    "TaintEngine",
    "RealTaintEngine",
    "NoOpTaintEngine",
]
