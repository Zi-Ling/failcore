# failcore/cli/renderers/__init__.py
"""
Renderers for FailCore Views

Renderers convert View models into display formats:
- Text: Plain text output (default, stable)
- Json: JSON output (for CI/tools)
- Markdown: Markdown output (for GitHub issues)
"""

from .text import TextRenderer
from .json import JsonRenderer

__all__ = [
    "TextRenderer",
    "JsonRenderer",
]
