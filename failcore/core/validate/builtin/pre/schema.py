# failcore/core/validate/builtin/pre/schema.py
"""
Type validation validators for input parameters

Lightweight type gate focusing on:
1. Basic type matching (isinstance)
2. Required fields
3. Container type checking (first-level only)
4. Basic boundaries (max_length/max_items)

For complex validation (email/url/nested schemas), use Pydantic models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union, Type

from failcore.core.validate.validator import BaseValidator
from failcore.core.validate.contracts import Context, Decision, ValidatorConfig, DecisionOutcome, RiskLevel


class TypeRequiredFieldsValidator(BaseValidator):
    """
    Required fields validator.
    
    Checks that all required fields are present in the parameters.
    """
    
    @property
    def id(self) -> str:
        return "type_required_fields"
    
    @property
    def domain(self) -> str:
        return "type"
    
    @property
    def config_schema(self) -> Optional[Dict[str, Any]]:
        """JSON schema for validator configuration"""
        return {
            "type": "object",
            "properties": {
                "required_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Names of required fields",
                },
            },
            "required": ["required_fields"],
        }
    
    @property
    def default_config(self) -> Dict[str, Any]:
        return {
            "required_fields": [],
        }
    
    def evaluate(
        self,
        context: Context,
        config: Optional[ValidatorConfig] = None,
    ) -> List[Decision]:
        """
        Evaluate required fields validation
        
        Args:
            context: Validation context (tool, params, etc.)
            config: Validator configuration (required_fields)
            
        Returns:
            List of Decision objects (empty if validation passes)
        """
        decisions: List[Decision] = []
        
        # Get configuration
        cfg = self._get_config(config)
        required_fields = cfg.get("required_fields", [])
        
        if not required_fields:
            # No required fields configured, skip check
            return []
        
        # Check for missing fields
        missing = [field for field in required_fields if field not in context.params]
        
        if missing:
            return [
                Decision.block(
                    code="FC_TYPE_REQUIRED_FIELDS_MISSING",
                    validator_id=self.id,
                    message=f"Missing required fields: {', '.join(missing)}",
                    evidence={"missing_fields": missing},
                    tool=context.tool,
                    step_id=context.step_id,
                )
            ]
        
        # All required fields present
        return []
    
    def _get_config(self, config: Optional[ValidatorConfig]) -> Dict[str, Any]:
        """Get merged configuration"""
        default = self.default_config
        if config and config.config:
            default.update(config.config)
        return default


__all__ = [
    "TypeRequiredFieldsValidator",
]
