# failcore/web/__init__.py
"""
FailCore Web UI - FastAPI + HTMX interface for viewing traces and reports.
"""

__all__ = ["create_app"]

from .app import create_app
