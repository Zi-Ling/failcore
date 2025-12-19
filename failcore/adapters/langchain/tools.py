# failcore/adapters/langchain/tools.py
from __future__ import annotations

import hashlib
import re
from typing import Any, Callable, Dict, Optional, Type, Union, get_args, get_origin

from pydantic import BaseModel, Field, create_model

try:
    from langchain_core.tools import StructuredTool
except ImportError:
    StructuredTool = None  # type: ignore


class UnsupportedSchemaError(ValueError):
    """Raised when the adapter receives a schema shape/type it does not support."""


# ----------------------------
# Naming utilities
# ----------------------------

def _sanitize_identifier(name: str) -> str:
    name = re.sub(r"[^0-9a-zA-Z_]", "_", name)
    if name and name[0].isdigit():
        name = f"_{name}"
    return name or "X"


def _stable_suffix(*parts: str, length: int = 8) -> str:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return h[:length]


def _make_model_name(tool_name: str, version: str) -> str:
    # Stable + collision-resistant across tools/libraries
    base = _sanitize_identifier(tool_name)
    suf = _stable_suffix(tool_name, version)
    return f"FailCore_{base}_{suf}_Args"


# ----------------------------
# Schema -> python type
# ----------------------------

def _python_type_from_jsonschema(prop: Dict[str, Any]) -> Type[Any]:
    """
    Restricted JSONSchema/OpenAPI-ish -> Python type mapping.

    Supported:
      - string, integer, number, boolean
      - nullable (type includes "null" or nullable:true)
      - enum (basic inference only; no Literal to keep stable)

    Not supported (fail fast):
      - array, object, oneOf/anyOf/allOf, $ref, nested schemas, etc.
    """
    if any(k in prop for k in ("oneOf", "anyOf", "allOf", "$ref")):
        raise UnsupportedSchemaError(f"Unsupported complex schema keyword in: {prop}")

    t = prop.get("type")

    # Handle type as list (e.g. ["string","null"])
    nullable = False
    if isinstance(t, list):
        if "null" in t:
            nullable = True
            t = [x for x in t if x != "null"]
            if len(t) != 1:
                raise UnsupportedSchemaError(f"Unsupported union type list: {prop.get('type')}")
            t = t[0]

    # OpenAPI nullable
    if prop.get("nullable") is True:
        nullable = True

    # Primitive mapping
    if t == "string":
        py = str
    elif t == "integer":
        py = int
    elif t == "number":
        py = float
    elif t == "boolean":
        py = bool
    elif t is None:
        # Allow missing type only when enum exists
        if "enum" in prop:
            enum_vals = [v for v in prop.get("enum", []) if v is not None]
            if not enum_vals:
                py = str
            else:
                v0 = enum_vals[0]
                if isinstance(v0, bool):
                    py = bool
                elif isinstance(v0, int):
                    py = int
                elif isinstance(v0, float):
                    py = float
                else:
                    py = str
        else:
            raise UnsupportedSchemaError(f"Missing 'type' in property schema: {prop}")
    else:
        # Explicitly reject complex types for now
        raise UnsupportedSchemaError(f"Unsupported schema type: {t}")

    if nullable:
        return Optional[py]  # type: ignore[return-value]
    return py


def _ensure_optional(tp: Type[Any]) -> Type[Any]:
    origin = get_origin(tp)
    if origin is Union and type(None) in get_args(tp):
        return tp
    return Optional[tp]  # type: ignore[return-value]


def _pydantic_model_from_schema(tool_name: str, version: str, schema: Dict[str, Any]) -> Type[BaseModel]:
    """
    Build a Pydantic model from restricted schema:
      {"properties": {...}, "required": [...]}

    Rules:
      - required field: type T, default=...
      - optional field: Optional[T], default=None
      - unsupported schema -> raise UnsupportedSchemaError (fail fast)
    """
    props = schema.get("properties", {}) or {}
    required = set(schema.get("required", []) or [])

    if not isinstance(props, dict):
        raise UnsupportedSchemaError("Schema 'properties' must be a dict.")

    fields: Dict[str, Any] = {}
    for key, prop_schema in props.items():
        if not isinstance(prop_schema, dict):
            raise UnsupportedSchemaError(f"Property schema for '{key}' must be a dict.")

        py_type = _python_type_from_jsonschema(prop_schema)

        if key in required:
            default = ...
        else:
            py_type = _ensure_optional(py_type)
            default = None

        desc = prop_schema.get("description", "") or ""
        fields[key] = (py_type, Field(default=default, description=desc))

    model_name = _make_model_name(tool_name, version)
    return create_model(model_name, **fields)  # type: ignore[return-value]


# ----------------------------
# Public API
# ----------------------------

# invoke signature:
#   invoke(tool_name, version, schema, fn, args_dict) -> Any
InvokeFn = Callable[[str, str, Dict[str, Any], Callable[..., Any], Dict[str, Any]], Any]


def to_langchain_tool(
    tool_name: str,
    description: str,
    schema: Dict[str, Any],
    fn: Callable[..., Any],
    *,
    version: str = "1.0",
    invoke: Optional[InvokeFn] = None,
    annotate_description_with_version: bool = True,
) -> StructuredTool:
    """
    Convert a FailCore ToolSpec into a LangChain StructuredTool.

    Why version matters:
      - When tool params/schema change, version can be used by your tool_runner fingerprint
        to prevent unsafe replay across incompatible versions.

    Why invoke injection matters:
      - Keeps this adapter thin. You can later inject tool_runner here without rewriting tools.py.

    Defaults:
      - If invoke is None: call fn(**kwargs) directly.
    """
    if StructuredTool is None:
        raise ImportError(
            "langchain-core is required for LangChain adapter. "
            "Install it with: pip install failcore[langchain]"
        )
    
    args_model = _pydantic_model_from_schema(tool_name, version, schema)

    if invoke is None:
        def invoke(tool_name_: str, version_: str, schema_: Dict[str, Any], fn_: Callable[..., Any], args_: Dict[str, Any]) -> Any:
            return fn_(**args_)

    # Keep description stable; optionally annotate with version
    desc = description
    if annotate_description_with_version:
        desc = f"{description}\n\n[failcore] version={version}"

    def _wrapped(**kwargs: Any) -> Any:
        # Single choke point where you’ll later plug in FailCore tool_runner:
        # invoke(tool_name, version, schema, fn, kwargs)
        return invoke(tool_name, version, schema, fn, dict(kwargs))

    return StructuredTool.from_function(
        name=tool_name,
        description=desc,
        args_schema=args_model,
        func=_wrapped,
    )
