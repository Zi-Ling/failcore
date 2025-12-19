# /failcore/adapters/langchain/__init__.py
"""
LangChain adapters.

核心组件：
- LangChainExecutor: FailCore 执行器包装，用于执行 LangChain 工具
- wrap_langchain_tool_for_failcore: 工具转换函数

注意：
    使用此适配器需要安装 langchain-core：
    pip install failcore[langchain]
"""

# 检查 langchain-core 是否可用
try:
    import langchain_core
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False

from .tool_runner import (
    LangChainExecutor,
    ToolResult,
    ToolExecutionError,
    wrap_langchain_tool_for_failcore,
)

__all__ = [
    # Executor
    "LangChainExecutor",
    "ToolResult",
    "ToolExecutionError",
    "wrap_langchain_tool_for_failcore",
]

# 如果 langchain-core 未安装，发出警告
if not _LANGCHAIN_AVAILABLE:
    import warnings
    warnings.warn(
        "langchain-core not installed. LangChain adapter may not work properly. "
        "Install with: pip install failcore[langchain]",
        ImportWarning,
        stacklevel=2
    )