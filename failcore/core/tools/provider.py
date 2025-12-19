# failcore/core/tools/provider.py
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable


ToolFn = Callable[..., Any]


@runtime_checkable
class ToolProvider(Protocol):
    """
    ToolProvider is the only thing the Executor should depend on.

    Minimal contract (v0.1):
      - get(name) -> callable | None

    Optional contract (still v0.1-safe):
      - list() -> list[str]         (for debugging / show)
      - describe(name) -> dict      (for schema/introspection later)
    """

    def get(self, name: str) -> Optional[ToolFn]:
        ...

    # Optional helpers (executor should not require these)
    def list(self) -> List[str]:
        ...

    def describe(self, name: str) -> Dict[str, Any]:
        ...
