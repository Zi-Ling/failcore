# failcore/api/presets.py
"""
Presets collection - turn complexity into switches

Three types of presets:
1. validators - precondition/postcondition validators
2. policy - policies (resource access, cost control, etc.)
3. tools - demo tools (minimal set, avoid builtins explosion)
"""

from typing import List, Optional
from ..core.validate.validator import (
    ValidatorRegistry,
    PreconditionValidator,
    file_exists_precondition,
    file_not_exists_precondition,
    dir_exists_precondition,
    param_not_empty_precondition,
)
from ..core.policy.policy import (
    Policy,
    ResourcePolicy,
    CostPolicy,
    CompositePolicy,
)


# ===========================
# Validator Presets
# ===========================

def fs_safe() -> ValidatorRegistry:
    """
    File system safety validator preset
    
    Common file preconditions:
    - Existence checks
    - Path normalization checks
    - Prevent path traversal, etc.
    
    Returns:
        ValidatorRegistry: Configured validator registry
    
    Example:
        >>> from failcore import Session, presets
        >>> session = Session(validator=presets.fs_safe())
    """
    registry = ValidatorRegistry()
    
    # Read file tools: file must exist
    for tool in ["read_file", "file.read"]:
        registry.register_precondition(
            tool,
            file_exists_precondition("path")
        )
    
    # Write file tools: parameters must not be empty
    for tool in ["write_file", "file.write"]:
        registry.register_precondition(
            tool,
            param_not_empty_precondition("path")
        )
        registry.register_precondition(
            tool,
            param_not_empty_precondition("content")
        )
    
    # Create file: file must not already exist
    for tool in ["create_file", "file.create"]:
        registry.register_precondition(
            tool,
            file_not_exists_precondition("path")
        )
    
    # Directory operations: directory must exist
    for tool in ["list_dir", "dir.list"]:
        registry.register_precondition(
            tool,
            dir_exists_precondition("path")
        )
    
    return registry


def net_safe() -> ValidatorRegistry:
    """
    Network safety validator preset
    
    Network validations:
    - Timeout checks
    - Domain whitelist
    - Retry policies
    
    Returns:
        ValidatorRegistry: Configured validator registry
    
    Example:
        >>> session = Session(validator=presets.net_safe())
    """
    registry = ValidatorRegistry()
    
    # HTTP requests: URL must not be empty
    for tool in ["http_get", "http.get", "http_post", "http.post"]:
        registry.register_precondition(
            tool,
            param_not_empty_precondition("url")
        )
    
    return registry


# ===========================
# Policy Presets
# ===========================

def read_only() -> Policy:
    """
    Read-only policy preset - only allow read operations
    
    Deny all write operations (write, delete, mkdir, etc.)
    
    Returns:
        Policy: Read-only policy
    
    Example:
        >>> session = Session(policy=presets.read_only())
    """
    class ReadOnlyPolicy:
        def allow(self, step, ctx):
            tool = step.tool
            
            # Deny write operations
            write_tools = [
                "write", "delete", "remove", "mkdir", "rmdir",
                "file.write", "file.delete", "file.create",
                "dir.create", "dir.delete", "dir.remove",
                "http.post", "http.put", "http.delete", "http.patch"
            ]
            
            for pattern in write_tools:
                if pattern in tool.lower():
                    return False, f"Read-only mode: write operation denied for {tool}"
            
            return True, ""
    
    return ReadOnlyPolicy()


def safe_write(sandbox_root: str) -> Policy:
    """
    Safe write policy preset - file writes only allowed in sandbox directory
    
    Args:
        sandbox_root: Sandbox root directory path
    
    Returns:
        Policy: Safe write policy
    
    Example:
        >>> session = Session(
        ...     policy=presets.safe_write("/tmp/sandbox"),
        ...     sandbox="/tmp/sandbox"
        ... )
    """
    return ResourcePolicy(
        name="safe_write",
        allowed_paths=[sandbox_root]
    )


def dangerous_disabled() -> Policy:
    """
    Dangerous operations disabled preset - delete/overwrite denied by default
    
    Deny all dangerous operations:
    - delete/remove operations
    - overwrite operations
    - system/shell commands
    
    Returns:
        Policy: Dangerous operations disabled policy
    
    Example:
        >>> session = Session(policy=presets.dangerous_disabled())
    """
    class DangerousDisabledPolicy:
        def allow(self, step, ctx):
            tool = step.tool
            
            # Deny dangerous operations
            dangerous = [
                "delete", "remove", "rm",
                "overwrite",
                "system", "shell", "exec", "eval"
            ]
            
            for pattern in dangerous:
                if pattern in tool.lower():
                    return False, f"Dangerous operation disabled: {tool}"
            
            return True, ""
    
    return DangerousDisabledPolicy()


def cost_limit(
    max_steps: int = 1000,
    max_duration_seconds: float = 300.0
) -> Policy:
    """
    Cost limit policy preset
    
    Args:
        max_steps: Maximum number of steps (default 1000)
        max_duration_seconds: Maximum execution time in seconds (default 300)
    
    Returns:
        Policy: Cost limit policy
    
    Example:
        >>> session = Session(policy=presets.cost_limit(max_steps=100))
    """
    return CostPolicy(
        max_total_steps=max_steps,
        max_duration_seconds=max_duration_seconds
    )


def combine_policies(*policies: Policy) -> Policy:
    """
    Combine multiple policies
    
    All policies must pass for execution to be allowed.
    
    Args:
        *policies: List of policies to combine
    
    Returns:
        Policy: Combined policy
    
    Example:
        >>> policy = presets.combine_policies(
        ...     presets.read_only(),
        ...     presets.cost_limit(max_steps=100)
        ... )
        >>> session = Session(policy=policy)
    """
    return CompositePolicy(
        name="combined",
        policies=list(policies)
    )


# ===========================
# Tools Presets (minimal set)
# ===========================

def demo_tools():
    """
    Demo tool set - for testing and demonstration only
    
    Includes:
    - divide: Division (demonstrates failure on divide-by-zero)
    - echo: Echo input (demonstrates success)
    - fail: Intentional failure (for testing error handling)
    
    Returns:
        dict: Tool name -> tool function mapping
    
    Example:
        >>> from failcore import Session, presets
        >>> session = Session()
        >>> for name, fn in presets.demo_tools().items():
        ...     session.register(name, fn)
        >>> result = session.call("divide", a=6, b=2)
    
    Note:
        These are not builtin tools, just a demo collection.
        In real projects, users should register their own tools.
    """
    def divide(a: float, b: float) -> float:
        """Division (fails when b=0)"""
        return a / b
    
    def echo(text: str) -> str:
        """Echo input text"""
        return text
    
    def fail(message: str = "Intentional failure") -> None:
        """Intentionally fail"""
        raise RuntimeError(message)
    
    return {
        "divide": divide,
        "echo": echo,
        "fail": fail,
    }
