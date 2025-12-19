# failcore/adapters/langchain/tool_runner.py
"""
LangChain Tool 的 FailCore 适配器。

这是唯一的插入点：把 LangChain 的 tool.invoke(args) 替换为 FailCore.execute()
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from dataclasses import dataclass

try:
    from langchain_core.tools import BaseTool
except ImportError:
    BaseTool = None  # type: ignore

from failcore.core.step import Step, RunContext
from failcore.core.executor.executor import Executor


@dataclass
class ToolResult:
    """工具执行结果（统一格式）"""
    success: bool
    result: Any = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    step_id: str = ""
    duration_ms: int = 0


class LangChainExecutor:
    """
    LangChain Tool 的 FailCore 执行器。
    
    用法：
        executor = LangChainExecutor(
            failcore_executor=executor,
            run_id="agent_run_123"
        )
        
        # 替换 tool.invoke(tool_input)
        result = executor.execute_tool(tool, tool_input)
    """
    
    def __init__(
        self,
        failcore_executor: Executor,
        run_id: str,
        run_context: Optional[RunContext] = None
    ):
        """
        初始化。
        
        Args:
            failcore_executor: FailCore 执行器（已配置 validator, policy, recorder）
            run_id: 本次 agent 运行的 ID
            run_context: 可选的 RunContext（不提供则自动创建）
        """
        self.failcore_executor = failcore_executor
        self.run_id = run_id
        self.run_context = run_context or RunContext(run_id=run_id)
        self.step_counter = 0
        self._tool_registry: Dict[str, Any] = {}  # tool_name -> tool_fn
    
    def register_langchain_tool(self, tool: Any) -> None:
        """
        注册 LangChain Tool。
        
        Args:
            tool: LangChain BaseTool 实例
        """
        if BaseTool and isinstance(tool, BaseTool):
            tool_name = tool.name
            # 包装 tool.invoke 为普通函数
            def tool_fn(**kwargs):
                return tool.invoke(kwargs)
            
            self._tool_registry[tool_name] = tool_fn
            
            # 注册到 FailCore 的工具注册表
            if hasattr(self.failcore_executor.tools, 'register'):
                self.failcore_executor.tools.register(tool_name, tool_fn)
        else:
            raise ValueError("Tool must be a LangChain BaseTool instance")
    
    def execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        step_id: Optional[str] = None
    ) -> ToolResult:
        """
        执行工具（FailCore 包装）。
        
        这是核心方法：走完整的 Validate → Policy → Execute → Trace 流程。
        
        Args:
            tool_name: 工具名称
            tool_input: 工具参数
            step_id: 可选的步骤ID（不提供则自动生成）
            
        Returns:
            ToolResult
        """
        # 生成 step_id
        if step_id is None:
            self.step_counter += 1
            step_id = f"{self.step_counter}_{tool_name}"
        
        # 构造 FailCore Step
        step = Step(
            id=step_id,
            tool=tool_name,
            params=tool_input
        )
        
        # 执行（走完整流程）
        # Resolve → Validate → Policy → Execute → Trace
        result = self.failcore_executor.execute(step, self.run_context)
        
        # 转换为统一格式
        if result.status.value == "ok":
            return ToolResult(
                success=True,
                result=result.output.value if result.output else None,
                step_id=result.step_id,
                duration_ms=result.duration_ms
            )
        else:
            return ToolResult(
                success=False,
                error_code=result.error.error_code if result.error else "UNKNOWN",
                error_message=result.error.message if result.error else "",
                step_id=result.step_id,
                duration_ms=result.duration_ms
            )
    
    def execute_langchain_tool(
        self,
        tool: Any,
        tool_input: Dict[str, Any],
        step_id: Optional[str] = None
    ) -> ToolResult:
        """
        直接执行 LangChain Tool（便捷方法）。
        
        Args:
            tool: LangChain BaseTool 实例
            tool_input: 工具参数
            step_id: 可选的步骤ID
            
        Returns:
            ToolResult
        """
        if BaseTool and isinstance(tool, BaseTool):
            tool_name = tool.name
            
            # 临时注册（如果未注册）
            if tool_name not in self._tool_registry:
                self.register_langchain_tool(tool)
            
            return self.execute_tool(tool_name, tool_input, step_id)
        else:
            raise ValueError("Tool must be a LangChain BaseTool instance")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        return {
            "run_id": self.run_id,
            "total_steps": self.step_counter,
            "registered_tools": list(self._tool_registry.keys())
        }


class ToolExecutionError(Exception):
    """工具执行错误（用于 LangChain 异常传播）"""
    
    def __init__(self, result: ToolResult):
        self.result = result
        super().__init__(f"{result.error_code}: {result.error_message}")


def wrap_langchain_tool_for_failcore(tool: Any) -> tuple[str, Any]:
    """
    将 LangChain Tool 转换为 FailCore 工具函数。
    
    Args:
        tool: LangChain BaseTool 实例
        
    Returns:
        (tool_name, tool_fn) 元组
    """
    if not BaseTool or not isinstance(tool, BaseTool):
        raise ValueError("Tool must be a LangChain BaseTool instance")
    
    tool_name = tool.name
    
    def tool_fn(**kwargs):
        """FailCore 兼容的工具函数"""
        return tool.invoke(kwargs)
    
    return tool_name, tool_fn

