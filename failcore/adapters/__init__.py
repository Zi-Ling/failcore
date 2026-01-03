# failcore/adapters/__init__.py



from .langchain import is_langchain_tool, is_langchain_available, map_langchain_tool, to_langchain_tool, guard_tool



__all__ = [
    # Type detection
    "is_langchain_tool",
    "is_langchain_available",

    # Core adapter (main path)
    "map_langchain_tool",  # Low-level mapper

    # Optional facade (for Agent compatibility)
    "guard_tool",         # Recommended public API
    "to_langchain_tool",  # Internal name (kept for compatibility)
]