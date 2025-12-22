# \failcore\core\tools\registry.py

from typing import Callable, Dict, Optional, Any

# ---------------------------
# Tool Registry
# ---------------------------

ToolFn = Callable[..., Any]


class ToolRegistry:
    """
    Minimal tools registry: maps tools name -> callable.
    """
    def __init__(self) -> None:
        self._tools: Dict[str, ToolFn] = {}

    def register(self, name: str, fn: ToolFn) -> None:
        if not name or not isinstance(name, str):
            raise ValueError("tools name must be non-empty str")
        if not callable(fn):
            raise ValueError("tools fn must be callable")
        self._tools[name] = fn

    def get(self, name: str) -> Optional[ToolFn]:
        return self._tools.get(name)
    
    def list(self) -> list[str]:
        """返回所有已注册的工具名称"""
        return list(self._tools.keys())
    
    def describe(self, name: str) -> Dict[str, Any]:
        """返回工具的描述信息"""
        fn = self._tools.get(name)
        if fn is None:
            return {}
        return {
            "name": name,
            "doc": fn.__doc__ or "",
            "callable": str(fn)
        }


# ---------------------------
# Builtin Registry Factory
# ---------------------------

def create_builtin_registry() -> ToolRegistry:
    """
    创建包含所有内置工具的注册表。
    
    Returns:
        ToolRegistry: 包含所有内置工具的注册表
    """
    from tools.builtin.file import register_file_tools
    from tools.builtin.http import register_http_tools
    from tools.builtin.string import register_string_tools
    from tools.builtin.json import register_json_tools
    
    registry = ToolRegistry()
    
    # 注册所有内置工具
    register_file_tools(registry)
    register_http_tools(registry)
    register_string_tools(registry)
    register_json_tools(registry)
    
    return registry

