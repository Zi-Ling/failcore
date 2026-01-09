"""
Data Loss Prevention (DLP)

Active defense module that intercepts sensitive data leakage at tool call boundaries
"""

from .policies import DLPAction, DLPPolicy, PolicyMatrix
from .patterns import SensitivePattern, PatternCategory, DLPPatternRegistry
from .middleware import DLPMiddleware

__all__ = [
    "DLPAction",
    "DLPPolicy",
    "PolicyMatrix",
    "SensitivePattern",
    "PatternCategory",
    "DLPPatternRegistry",
    "DLPMiddleware",
]
