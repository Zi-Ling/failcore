# failcore/core/policy/policy.py
"""
Policy core implementation with LLM-friendly suggestions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol
from pathlib import Path
import os
import time


@dataclass
class PolicyResult:
    """
    Policy check result (LLM-Friendly Design)
    
    The suggestion field is a first-class citizen, providing actionable fix guidance.
    """
    allowed: bool
    reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    # LLM-friendly fields
    suggestion: Optional[str] = None      # Actionable fix suggestion
    remediation: Optional[Dict[str, Any]] = None  # Structured fix with template vars
    
    @classmethod
    def allow(cls, reason: str = "Allowed") -> PolicyResult:
        """Create allow result"""
        return cls(allowed=True, reason=reason)
    
    @classmethod
    def deny(
        cls, 
        reason: str, 
        details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        remediation: Optional[Dict[str, Any]] = None,
    ) -> PolicyResult:
        """
        Create deny result with fix suggestion
        
        Args:
            reason: Denial reason
            details: Detailed information
            suggestion: Actionable fix suggestion (for LLM/human)
            remediation: Structured fix instructions (with template variables)
        """
        return cls(
            allowed=False, 
            reason=reason, 
            details=details or {},
            suggestion=suggestion,
            remediation=remediation,
        )


class PolicyDeny(Exception):
    """Policy denial exception"""
    def __init__(self, message: str, result: PolicyResult):
        super().__init__(message)
        self.result = result


class Policy(Protocol):
    """
    Policy protocol (Enhanced with LLM-Friendly Suggestions)
    
    Return value can be:
    - tuple[bool, str]: Legacy compatible (allowed, reason)
    - PolicyResult: Modern recommended (includes suggestion)
    """
    
    def allow(self, step: Any, ctx: Any) -> tuple[bool, str] | PolicyResult:
        """
        Check if execution is allowed.
        
        Args:
            step: Step object
            ctx: RunContext object
            
        Returns:
            tuple[bool, str] or PolicyResult
            - Legacy: (allowed, reason)
            - Modern: PolicyResult(allowed, reason, suggestion, remediation)
        """
        ...


@dataclass
class ResourcePolicy:
    """
    Resource access policy.
    
    Controls access to filesystem, network, and other resources.
    """
    name: str = "resource_policy"
    
    # Filesystem policy
    allowed_paths: List[str] = field(default_factory=list)  # Allowed paths
    denied_paths: List[str] = field(default_factory=list)   # Denied paths
    
    # Network policy
    allow_network: bool = True
    allowed_domains: List[str] = field(default_factory=list)  # Allowed domains
    denied_domains: List[str] = field(default_factory=list)   # Denied domains
    
    def allow(self, step: Any, ctx: Any) -> tuple[bool, str]:
        """Check resource access permissions"""
        tool_name = step.tool
        params = step.params
        
        # Check file operations
        if tool_name.startswith(("file.", "dir.")):
            path_param = params.get("path") or params.get("source") or params.get("destination")
            if path_param:
                result = self._check_file_access(path_param)
                if not result.allowed:
                    return False, result.reason
        
        # Check network operations
        if tool_name.startswith("http."):
            url = params.get("url", "")
            result = self._check_network_access(url)
            if not result.allowed:
                return False, result.reason
        
        return True, ""
    
    def _check_file_access(self, path: str) -> PolicyResult:
        """Check file access permissions"""
        abs_path = os.path.abspath(path)
        
        # Check deny list
        for denied in self.denied_paths:
            denied_abs = os.path.abspath(denied)
            if abs_path.startswith(denied_abs):
                return PolicyResult.deny(
                    f"Access denied to path: {path}",
                    {"path": abs_path, "denied": denied_abs}
                )
        
        # If allow list exists, check if path is in allow list
        if self.allowed_paths:
            allowed = False
            for allowed_path in self.allowed_paths:
                allowed_abs = os.path.abspath(allowed_path)
                if abs_path.startswith(allowed_abs):
                    allowed = True
                    break
            
            if not allowed:
                return PolicyResult.deny(
                    f"Path not in allow list: {path}",
                    {"path": abs_path, "allowed_paths": self.allowed_paths}
                )
        
        return PolicyResult.allow()
    
    def _check_network_access(self, url: str) -> PolicyResult:
        """检查网络访问权限"""
        if not self.allow_network:
            return PolicyResult.deny("网络访问被禁止")
        
        # 提取域名
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # 检查黑名单
        for denied in self.denied_domains:
            if domain.endswith(denied):
                return PolicyResult.deny(
                    f"禁止访问域名: {domain}",
                    {"domain": domain, "denied": denied}
                )
        
        # 如果有白名单，检查是否在白名单中
        if self.allowed_domains:
            allowed = False
            for allowed_domain in self.allowed_domains:
                if domain.endswith(allowed_domain):
                    allowed = True
                    break
            
            if not allowed:
                return PolicyResult.deny(
                    f"域名不在允许列表中: {domain}",
                    {"domain": domain, "allowed_domains": self.allowed_domains}
                )
        
        return PolicyResult.allow()


@dataclass
class CostPolicy:
    """
    成本控制策略。
    
    控制执行的成本，包括：
    - 调用次数限制
    - 执行时间限制
    - 并发限制
    """
    name: str = "cost_policy"
    
    # 全局限制
    max_total_steps: int = 1000  # 总步骤数限制
    max_duration_seconds: float = 300.0  # 总执行时间限制（秒）
    
    # 单工具限制
    max_calls_per_tool: Dict[str, int] = field(default_factory=dict)  # 每个工具的调用次数限制
    
    # 状态追踪
    _total_steps: int = field(default=0, init=False)
    _start_time: Optional[float] = field(default=None, init=False)
    _tool_calls: Dict[str, int] = field(default_factory=dict, init=False)
    
    def __post_init__(self) -> None:
        """初始化"""
        if self._start_time is None:
            self._start_time = time.time()
    
    def allow(self, step: Any, ctx: Any) -> tuple[bool, str]:
        """检查成本限制"""
        # 检查总步骤数
        if self._total_steps >= self.max_total_steps:
            return False, f"已达到最大步骤数限制: {self.max_total_steps}"
        
        # 检查总执行时间
        if self._start_time is not None:
            elapsed = time.time() - self._start_time
            if elapsed >= self.max_duration_seconds:
                return False, f"已达到最大执行时间限制: {self.max_duration_seconds}秒"
        
        # 检查单工具调用次数
        tool_name = step.tool
        if tool_name in self.max_calls_per_tool:
            current_calls = self._tool_calls.get(tool_name, 0)
            max_calls = self.max_calls_per_tool[tool_name]
            if current_calls >= max_calls:
                return False, f"工具 {tool_name} 已达到最大调用次数: {max_calls}"
        
        # 更新计数器
        self._total_steps += 1
        self._tool_calls[tool_name] = self._tool_calls.get(tool_name, 0) + 1
        
        return True, ""
    
    def reset(self) -> None:
        """重置计数器"""
        self._total_steps = 0
        self._start_time = time.time()
        self._tool_calls.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        elapsed = 0.0
        if self._start_time is not None:
            elapsed = time.time() - self._start_time
        
        return {
            "total_steps": self._total_steps,
            "elapsed_seconds": elapsed,
            "tool_calls": dict(self._tool_calls),
        }


@dataclass
class CompositePolicy:
    """
    组合策略。
    
    组合多个策略，所有策略都通过才允许执行。
    """
    name: str = "composite_policy"
    policies: List[Policy] = field(default_factory=list)
    
    def allow(self, step: Any, ctx: Any) -> tuple[bool, str]:
        """检查所有策略"""
        for policy in self.policies:
            allowed, reason = policy.allow(step, ctx)
            if not allowed:
                return False, f"{policy.__class__.__name__}: {reason}"
        
        return True, ""
    
    def add_policy(self, policy: Policy) -> None:
        """添加策略"""
        self.policies.append(policy)

