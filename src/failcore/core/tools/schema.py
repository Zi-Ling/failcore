# failcore/core/tools/schema.py
"""
工具 Schema 描述系统。

为工具提供结构化的元数据，包括：
- 参数定义和类型
- 返回值类型
- 文档说明
- 示例
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import inspect


class ParamType(str, Enum):
    """参数类型枚举"""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    ANY = "any"


@dataclass
class ParamSchema:
    """参数 schema"""
    name: str
    type: ParamType
    description: str = ""
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None  # 枚举值
    items: Optional[ParamType] = None  # 数组元素类型
    properties: Optional[Dict[str, "ParamSchema"]] = None  # 对象属性


@dataclass
class ToolSchema:
    """工具 schema"""
    name: str
    description: str
    parameters: List[ParamSchema] = field(default_factory=list)
    returns: Optional[ParamType] = None
    return_description: str = ""
    examples: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（兼容 OpenAI function calling）"""
        properties: Dict[str, Any] = {}
        required: List[str] = []
        
        for param in self.parameters:
            properties[param.name] = {
                "type": param.type.value,
                "description": param.description,
            }
            
            if param.enum:
                properties[param.name]["enum"] = param.enum
            
            if param.items:
                properties[param.name]["items"] = {"type": param.items.value}
            
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


def infer_param_type(annotation: Any) -> ParamType:
    """
    从 Python 类型注解推断参数类型。
    
    Args:
        annotation: 类型注解
        
    Returns:
        参数类型
    """
    if annotation is inspect.Parameter.empty:
        return ParamType.ANY
    
    # 处理字符串形式的注解
    if isinstance(annotation, str):
        annotation_lower = annotation.lower()
        if "str" in annotation_lower:
            return ParamType.STRING
        elif "int" in annotation_lower:
            return ParamType.INTEGER
        elif "float" in annotation_lower or "number" in annotation_lower:
            return ParamType.NUMBER
        elif "bool" in annotation_lower:
            return ParamType.BOOLEAN
        elif "list" in annotation_lower or "sequence" in annotation_lower:
            return ParamType.ARRAY
        elif "dict" in annotation_lower or "mapping" in annotation_lower:
            return ParamType.OBJECT
        return ParamType.ANY
    
    # 处理实际类型
    type_map = {
        str: ParamType.STRING,
        int: ParamType.INTEGER,
        float: ParamType.NUMBER,
        bool: ParamType.BOOLEAN,
        list: ParamType.ARRAY,
        dict: ParamType.OBJECT,
    }
    
    # 直接匹配
    if annotation in type_map:
        return type_map[annotation]
    
    # 处理泛型（typing.List, typing.Dict 等）
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        if origin is list:
            return ParamType.ARRAY
        elif origin is dict:
            return ParamType.OBJECT
    
    return ParamType.ANY


def extract_schema_from_function(fn: Callable, name: Optional[str] = None) -> ToolSchema:
    """
    从函数自动提取 schema。
    
    Args:
        fn: 函数对象
        name: 工具名称（默认使用函数名）
        
    Returns:
        工具 schema
    """
    sig = inspect.signature(fn)
    doc = inspect.getdoc(fn) or ""
    
    # 解析 docstring（简单版本）
    lines = doc.split("\n")
    description = lines[0] if lines else ""
    
    # 提取参数
    parameters: List[ParamSchema] = []
    for param_name, param in sig.parameters.items():
        # 跳过 *args, **kwargs
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        
        param_type = infer_param_type(param.annotation)
        has_default = param.default is not inspect.Parameter.empty
        
        parameters.append(ParamSchema(
            name=param_name,
            type=param_type,
            required=not has_default,
            default=param.default if has_default else None,
        ))
    
    # 推断返回类型
    return_type = None
    if sig.return_annotation is not inspect.Signature.empty:
        return_type = infer_param_type(sig.return_annotation)
    
    return ToolSchema(
        name=name or fn.__name__,
        description=description,
        parameters=parameters,
        returns=return_type,
    )


class SchemaRegistry:
    """Schema 注册表"""
    
    def __init__(self) -> None:
        self._schemas: Dict[str, ToolSchema] = {}
    
    def register(self, name: str, schema: ToolSchema) -> None:
        """注册 schema"""
        self._schemas[name] = schema
    
    def register_from_function(self, name: str, fn: Callable) -> ToolSchema:
        """从函数自动注册 schema"""
        schema = extract_schema_from_function(fn, name)
        self._schemas[name] = schema
        return schema
    
    def get(self, name: str) -> Optional[ToolSchema]:
        """获取 schema"""
        return self._schemas.get(name)
    
    def list(self) -> List[str]:
        """列出所有已注册的 schema"""
        return list(self._schemas.keys())
    
    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """转换为字典格式"""
        return {name: schema.to_dict() for name, schema in self._schemas.items()}

