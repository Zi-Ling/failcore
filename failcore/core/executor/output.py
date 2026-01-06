# failcore/core/executor/output.py
"""
Output Normalization - semantic normalization of tool execution results

This module handles semantic normalization of tool outputs into StepOutput.
It does NOT handle trace summarization (that's in trace/summarize.py).
"""

from typing import Any

from failcore.core.types.step import StepOutput, OutputKind, ArtifactRef


class OutputNormalizer:
    """
    Semantic normalization of tool execution results
    
    Converts tool function return values into StepOutput objects.
    This is about semantic understanding, not trace payload safety.
    """
    
    @staticmethod
    def normalize(out: Any) -> StepOutput:
        """
        Normalize tool output to StepOutput
        
        Args:
            out: Tool function return value
        
        Returns:
            StepOutput with appropriate kind
        
        Rules:
        - StepOutput -> return as-is
        - int/float/bool -> JSON
        - list of ArtifactRef -> ARTIFACTS
        - dict -> JSON
        - bytes/bytearray -> BYTES
        - str -> TEXT
        - other -> UNKNOWN
        """
        # If already StepOutput, trust it
        if isinstance(out, StepOutput):
            return out
        
        # Primitive types -> JSON
        if isinstance(out, (int, float, bool)):
            return StepOutput(kind=OutputKind.JSON, value=out)
        
        # List of artifacts -> ARTIFACTS
        if isinstance(out, list) and all(isinstance(x, ArtifactRef) for x in out):
            return StepOutput(kind=OutputKind.ARTIFACTS, value=None, artifacts=out)
        
        # Dict -> JSON
        if isinstance(out, dict):
            return StepOutput(kind=OutputKind.JSON, value=out)
        
        # Bytes -> BYTES
        if isinstance(out, (bytes, bytearray)):
            return StepOutput(kind=OutputKind.BYTES, value=f"<{len(out)} bytes>")
        
        # Str -> TEXT
        if isinstance(out, str):
            return StepOutput(kind=OutputKind.TEXT, value=out)
        
        # Fallback -> UNKNOWN
        return StepOutput(kind=OutputKind.UNKNOWN, value=out)


__all__ = ["OutputNormalizer"]
