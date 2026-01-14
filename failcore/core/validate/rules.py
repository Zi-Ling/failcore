"""
Data-Driven Rules Validator (Expression Rules)

This validator provides a fallback point for future community-rules.
It supports reading simple matching rules from the Policy's rules list.

Example rule format in policy:
rules:
  - id: "block_rm_rf"
    tool: "subprocess.run"
    param: "command"
    contains: "rm -rf"
    enforcement: "BLOCK"
  - id: "limit_file_size"
    tool: "open"
    param: "file"
    max_size: 10485760  # 10MB
    enforcement: "WARN"
"""

from typing import Any, Dict, List
import re
from pathlib import Path

from failcore.core.validate.builtin.output.contract import ValidationResult, PreconditionValidator


def matches_tool_pattern(tool_name: str, pattern: str) -> bool:
    """Check if tool name matches pattern (supports wildcards)"""
    if "*" in pattern or "?" in pattern:
        regex = pattern.replace("*", ".*").replace("?", ".")
        return bool(re.match(f"^{regex}$", tool_name))
    return tool_name == pattern


def matches_param_rule(param_value: Any, rule: Dict[str, Any]) -> bool:
    """Check if parameter value matches rule conditions"""
    # contains check
    if "contains" in rule:
        if isinstance(param_value, str):
            return rule["contains"] in param_value
        return False
    
    # regex check
    if "regex" in rule:
        if isinstance(param_value, str):
            return bool(re.search(rule["regex"], param_value))
        return False
    
    # equals check
    if "equals" in rule:
        return param_value == rule["equals"]
    
    # max_size check (for file paths)
    if "max_size" in rule:
        if isinstance(param_value, (str, Path)):
            try:
                path = Path(param_value)
                if path.exists() and path.is_file():
                    return path.stat().st_size > rule["max_size"]
            except Exception:
                pass
        return False
    
    return False


def expr_rules_validator(
    tool_name: str,
    params: Dict[str, Any],
    rules: List[Dict[str, Any]],
) -> ValidationResult:
    """
    Data-driven rules validator
    
    Args:
        tool_name: Tool name
        params: Tool parameters
        rules: List of rules, each rule contains:
            - id: Rule unique identifier
            - tool: Tool name pattern (supports wildcards)
            - param: Parameter name to check
            - contains/regex/equals/max_size: Match condition
            - enforcement: SHADOW/WARN/BLOCK
            - message: Optional custom message
    
    Returns:
        ValidationResult
    """
    for rule in rules:
        # Check if tool name matches
        if "tool" in rule and not matches_tool_pattern(tool_name, rule["tool"]):
            continue
        
        # Check parameter
        param_name = rule.get("param")
        if param_name and param_name in params:
            param_value = params[param_name]
            
            if matches_param_rule(param_value, rule):
                rule_id = rule.get("id", "unknown_rule")
                message = rule.get("message", f"Matched data rule: {rule_id}")
                enforcement = rule.get("enforcement", "WARN").upper()
                
                return ValidationResult(
                    passed=False,
                    code=f"FC_EXPR_{rule_id.upper()}",
                    message=message,
                    severity="error" if enforcement == "BLOCK" else "warning",
                    evidence={
                        "rule_id": rule_id,
                        "tool": tool_name,
                        "param": param_name,
                        "value": str(param_value)[:100],  # truncate long values
                        "matched_condition": {
                            k: v for k, v in rule.items()
                            if k in ["contains", "regex", "equals", "max_size"]
                        }
                    }
                )
    
    return ValidationResult(
        passed=True,
        code="FC_EXPR_OK",
        message="No data rules matched"
    )


# Export as PreconditionValidator
validate_expr_rules: PreconditionValidator = expr_rules_validator
