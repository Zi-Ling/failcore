# failcore/core/trace/summarize.py
"""
Trace Payload Summarization - safe truncation for trace events

This module provides safe summarization of values for trace payloads.
It ensures trace events don't contain huge payloads that could cause issues.

Design principle (adopts suggestion 3):
- OutputSummarizer belongs to trace module, not executor
- Can be reused by report, audit, webui without importing executor
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SummarizeConfig:
    """Configuration for summarization"""
    summarize_limit: int = 200  # Default truncation limit


class OutputSummarizer:
    """
    Trace payload safe summarization
    
    Provides methods to safely summarize values for trace events,
    ensuring payloads don't exceed reasonable size limits.
    """
    
    def __init__(self, config: Optional[SummarizeConfig] = None):
        """
        Initialize summarizer
        
        Args:
            config: SummarizeConfig instance (uses defaults if None)
        """
        self.config = config or SummarizeConfig()
    
    def summarize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Summarize parameters dict for trace payload
        
        Args:
            params: Parameters dict
        
        Returns:
            Summarized parameters dict
        """
        return {k: self.summarize_value(v) for k, v in params.items()}
    
    def summarize_output(self, output: Any) -> Dict[str, Any]:
        """
        Summarize output for trace payload
        
        Args:
            output: StepOutput or dict
        
        Returns:
            Summarized output dict
        """
        if hasattr(output, 'kind') and hasattr(output, 'value'):
            # StepOutput object
            return {
                "kind": output.kind.value if hasattr(output.kind, 'value') else str(output.kind),
                "value": self.summarize_value(output.value),
                "artifacts": [
                    {
                        "uri": a.uri,
                        "kind": a.kind,
                        "name": a.name,
                        "media_type": a.media_type
                    }
                    for a in (getattr(output, 'artifacts', None) or [])
                ],
            }
        elif isinstance(output, dict):
            # Already a dict
            return {
                "kind": output.get("kind", "unknown"),
                "value": self.summarize_value(output.get("value")),
                "artifacts": output.get("artifacts", []),
            }
        else:
            return {
                "kind": "unknown",
                "value": self.summarize_value(output),
                "artifacts": [],
            }
    
    def summarize_value(self, v: Any) -> Any:
        """
        Summarize a single value
        
        Args:
            v: Value to summarize
        
        Returns:
            Summarized value
        """
        if v is None or isinstance(v, (bool, int, float)):
            return v
        
        if isinstance(v, str):
            return self.truncate(v)
        
        if isinstance(v, (bytes, bytearray)):
            return f"<{len(v)} bytes>"
        
        if isinstance(v, dict):
            # Shallow summarize (limit depth)
            out: Dict[str, Any] = {}
            for i, (k, vv) in enumerate(v.items()):
                if i >= 20:
                    out["..."] = f"+{len(v)-20} more"
                    break
                out[str(k)] = self.summarize_value(vv)
            return out
        
        if isinstance(v, list):
            return [self.summarize_value(x) for x in v[:20]] + (["..."] if len(v) > 20 else [])
        
        return self.truncate(str(v))
    
    def truncate(self, s: str) -> str:
        """
        Truncate string to limit
        
        Args:
            s: String to truncate
        
        Returns:
            Truncated string with ellipsis if needed
        """
        limit = self.config.summarize_limit
        if len(s) <= limit:
            return s
        return s[:limit] + f"...(+{len(s)-limit} chars)"


__all__ = [
    "SummarizeConfig",
    "OutputSummarizer",
]
