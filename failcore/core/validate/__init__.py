# failcore/core/validate/__init__.py
"""
验证系统。

提供执行前的条件验证（前置拒绝机制）：
- 前置条件验证（precondition） - 在执行前拒绝不满足条件的操作
- 自定义验证器
- 验证结果追踪

注意：我们只做前置验证（拒绝），不做后置验证（修复）
"""

from .validator import (
    ValidationResult,
    ValidationError,
    Validator,
    PreconditionValidator,
    PostconditionValidator,
    ValidatorRegistry,
    # 常用验证器
    file_exists_precondition,
    file_not_exists_precondition,
    dir_exists_precondition,
    param_not_empty_precondition,
)

__all__ = [
    "ValidationResult",
    "ValidationError",
    "Validator",
    "PreconditionValidator",
    "PostconditionValidator",
    "ValidatorRegistry",
    # 常用验证器
    "file_exists_precondition",
    "file_not_exists_precondition",
    "dir_exists_precondition",
    "param_not_empty_precondition",
]

