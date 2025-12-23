# failcore/cli/renderers/__init__.py
"""
Renderers for FailCore Views

Renderers convert View models into display formats:
- Text: Plain text output (default, stable)
- Json: JSON output (for CI/tools)
- Html: HTML report output (for human-readable reports)
- Markdown: Markdown output (for GitHub issues)
"""

from .text import TextRenderer
from .json import JsonRenderer
from .html import HtmlRenderer

__all__ = [
    "TextRenderer",
    "JsonRenderer",
    "HtmlRenderer",
]
