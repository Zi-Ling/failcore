# failcore/core/policy/__init__.py
"""
策略系统。

提供执行策略控制，包括：
- 资源访问策略（文件路径、网络访问等）
- 成本控制策略（调用次数、时间限制等）
- 自定义策略
"""

from .policy import (
    Policy,
    PolicyResult,
    PolicyDeny,
    ResourcePolicy,
    CostPolicy,
    CompositePolicy,
)

__all__ = [
    "Policy",
    "PolicyResult",
    "PolicyDeny",
    "ResourcePolicy",
    "CostPolicy",
    "CompositePolicy",
]
