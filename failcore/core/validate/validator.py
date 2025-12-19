# failcore/core/validate/validator.py
"""
验证器核心实现。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol
from enum import Enum


class ValidationType(str, Enum):
    """验证类型"""
    PRECONDITION = "precondition"  # 前置条件
    POSTCONDITION = "postcondition"  # 后置条件
    INVARIANT = "invariant"  # 不变量（保留）


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success(cls, message: str = "验证通过") -> ValidationResult:
        """创建成功结果"""
        return cls(valid=True, message=message)
    
    @classmethod
    def failure(cls, message: str, details: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """创建失败结果"""
        return cls(valid=False, message=message, details=details or {})


class ValidationError(Exception):
    """验证失败异常"""
    def __init__(self, message: str, result: ValidationResult):
        super().__init__(message)
        self.result = result


class Validator(Protocol):
    """验证器协议"""
    
    def validate(self, context: Dict[str, Any]) -> ValidationResult:
        """
        执行验证。
        
        Args:
            context: 验证上下文（包含 step, params, result 等）
            
        Returns:
            验证结果
        """
        ...


@dataclass
class PreconditionValidator:
    """
    前置条件验证器。
    
    在工具执行前检查条件是否满足，例如：
    - 文件是否存在
    - 参数是否合法
    - 资源是否可用
    """
    name: str
    condition: Callable[[Dict[str, Any]], bool]
    message: str = ""
    
    def validate(self, context: Dict[str, Any]) -> ValidationResult:
        """执行验证"""
        try:
            if self.condition(context):
                return ValidationResult.success(f"前置条件 '{self.name}' 满足")
            else:
                msg = self.message or f"前置条件 '{self.name}' 不满足"
                return ValidationResult.failure(msg, {"condition": self.name})
        except Exception as e:
            return ValidationResult.failure(
                f"前置条件 '{self.name}' 检查失败: {e}",
                {"condition": self.name, "error": str(e)}
            )


@dataclass
class PostconditionValidator:
    """
    后置条件验证器。
    
    在工具执行后检查结果是否符合预期，例如：
    - 文件是否已创建
    - 返回值是否正确
    - 副作用是否符合预期
    """
    name: str
    condition: Callable[[Dict[str, Any]], bool]
    message: str = ""
    
    def validate(self, context: Dict[str, Any]) -> ValidationResult:
        """执行验证"""
        try:
            if self.condition(context):
                return ValidationResult.success(f"后置条件 '{self.name}' 满足")
            else:
                msg = self.message or f"后置条件 '{self.name}' 不满足"
                return ValidationResult.failure(msg, {"condition": self.name})
        except Exception as e:
            return ValidationResult.failure(
                f"后置条件 '{self.name}' 检查失败: {e}",
                {"condition": self.name, "error": str(e)}
            )


class ValidatorRegistry:
    """验证器注册表"""
    
    def __init__(self) -> None:
        # tool_name -> (preconditions, postconditions)
        self._validators: Dict[str, tuple[List[Validator], List[Validator]]] = {}
    
    def register_precondition(self, tool_name: str, validator: Validator) -> None:
        """注册前置条件验证器"""
        if tool_name not in self._validators:
            self._validators[tool_name] = ([], [])
        self._validators[tool_name][0].append(validator)
    
    def register_postcondition(self, tool_name: str, validator: Validator) -> None:
        """注册后置条件验证器"""
        if tool_name not in self._validators:
            self._validators[tool_name] = ([], [])
        self._validators[tool_name][1].append(validator)
    
    def get_preconditions(self, tool_name: str) -> List[Validator]:
        """获取前置条件验证器列表"""
        if tool_name not in self._validators:
            return []
        return self._validators[tool_name][0]
    
    def get_postconditions(self, tool_name: str) -> List[Validator]:
        """获取后置条件验证器列表"""
        if tool_name not in self._validators:
            return []
        return self._validators[tool_name][1]
    
    def validate_preconditions(self, tool_name: str, context: Dict[str, Any]) -> List[ValidationResult]:
        """验证所有前置条件"""
        validators = self.get_preconditions(tool_name)
        return [v.validate(context) for v in validators]
    
    def validate_postconditions(self, tool_name: str, context: Dict[str, Any]) -> List[ValidationResult]:
        """验证所有后置条件"""
        validators = self.get_postconditions(tool_name)
        return [v.validate(context) for v in validators]
    
    def has_validators(self, tool_name: str) -> bool:
        """检查工具是否有验证器"""
        if tool_name not in self._validators:
            return False
        pre, post = self._validators[tool_name]
        return len(pre) > 0 or len(post) > 0
    
    def has_preconditions(self, tool_name: str) -> bool:
        """检查工具是否有前置条件"""
        if tool_name not in self._validators:
            return False
        return len(self._validators[tool_name][0]) > 0


# 常用的前置条件验证器
def file_exists_precondition(param_name: str = "path") -> PreconditionValidator:
    """文件必须存在的前置条件"""
    import os
    return PreconditionValidator(
        name=f"file_exists_{param_name}",
        condition=lambda ctx: os.path.isfile(ctx["params"].get(param_name, "")),
        message=f"文件不存在: {param_name}"
    )


def file_not_exists_precondition(param_name: str = "path") -> PreconditionValidator:
    """文件必须不存在的前置条件"""
    import os
    return PreconditionValidator(
        name=f"file_not_exists_{param_name}",
        condition=lambda ctx: not os.path.exists(ctx["params"].get(param_name, "")),
        message=f"文件已存在: {param_name}"
    )


def dir_exists_precondition(param_name: str = "path") -> PreconditionValidator:
    """目录必须存在的前置条件"""
    import os
    return PreconditionValidator(
        name=f"dir_exists_{param_name}",
        condition=lambda ctx: os.path.isdir(ctx["params"].get(param_name, "")),
        message=f"目录不存在: {param_name}"
    )


def param_not_empty_precondition(param_name: str) -> PreconditionValidator:
    """参数不能为空的前置条件"""
    return PreconditionValidator(
        name=f"param_not_empty_{param_name}",
        condition=lambda ctx: bool(ctx["params"].get(param_name)),
        message=f"参数不能为空: {param_name}"
    )

