# failcore/core/validate/builtin/pre/resource.py
"""
Resource quota validators

Prevent resource exhaustion attacks:
1. File size limits
2. Payload size limits
3. Collection size limits (prevent explosion)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from failcore.core.validate.validator import BaseValidator
from failcore.core.validate.contracts import Context, Decision, ValidatorConfig, DecisionOutcome, RiskLevel


class ResourceFileSizeValidator(BaseValidator):
    """
    File size limit validator.
    
    Checks file size before reading/processing to prevent memory exhaustion.
    """
    
    @property
    def id(self) -> str:
        return "resource_file_size"
    
    @property
    def domain(self) -> str:
        return "resource"
    
    @property
    def config_schema(self) -> Optional[Dict[str, Any]]:
        """JSON schema for validator configuration"""
        return {
            "type": "object",
            "properties": {
                "param_name": {
                    "type": "string",
                    "description": "Parameter name containing file path (default: 'path')",
                },
                "max_bytes": {
                    "type": "integer",
                    "description": "Maximum allowed file size in bytes (default: 10485760 = 10MB)",
                },
            },
        }
    
    @property
    def default_config(self) -> Dict[str, Any]:
        return {
            "param_name": "path",
            "max_bytes": 10 * 1024 * 1024,  # 10MB default
        }
    
    def evaluate(
        self,
        context: Context,
        config: Optional[ValidatorConfig] = None,
    ) -> List[Decision]:
        """
        Evaluate file size validation
        
        Args:
            context: Validation context (tool, params, etc.)
            config: Validator configuration (param_name, max_bytes)
            
        Returns:
            List of Decision objects (empty if validation passes)
        """
        decisions: List[Decision] = []
        
        # Get configuration
        cfg = self._get_config(config)
        param_name = cfg.get("param_name", "path")
        max_bytes = cfg.get("max_bytes", 10 * 1024 * 1024)
        
        # Check if parameter exists
        if param_name not in context.params:
            # Parameter not provided, skip check
            return []
        
        file_path = context.params[param_name]
        
        if not isinstance(file_path, str):
            return [
                Decision.block(
                    code="FC_RES_FILE_SIZE_PARAM_TYPE",
                    validator_id=self.id,
                    message=f"Path parameter '{param_name}' must be a string",
                    evidence={
                        "param": param_name,
                        "got": type(file_path).__name__,
                    },
                    tool=context.tool,
                    step_id=context.step_id,
                )
            ]
        
        # Check if file exists
        if not os.path.exists(file_path):
            # Don't fail here - let the tool handle non-existent files
            return []
        
        # Check if it's a file (not directory)
        if not os.path.isfile(file_path):
            # Not a file, skip check
            return []
        
        try:
            file_size = os.path.getsize(file_path)
            
            if file_size > max_bytes:
                return [
                    Decision.block(
                        code="FC_RES_FILE_SIZE_EXCEEDED",
                        validator_id=self.id,
                        message=f"File size {file_size} bytes exceeds limit {max_bytes} bytes",
                        evidence={
                            "path": file_path,
                            "size_bytes": file_size,
                            "max_bytes": max_bytes,
                            "size_mb": round(file_size / 1024 / 1024, 2),
                            "max_mb": round(max_bytes / 1024 / 1024, 2),
                        },
                        tool=context.tool,
                        step_id=context.step_id,
                    )
                ]
            
            # File size check passed
            return []
            
        except Exception as e:
            return [
                Decision.block(
                    code="FC_RES_FILE_SIZE_CHECK_ERROR",
                    validator_id=self.id,
                    message=f"File size check error: {str(e)}",
                    evidence={
                        "path": file_path,
                        "error": str(e),
                    },
                    tool=context.tool,
                    step_id=context.step_id,
                )
            ]
    
    def _get_config(self, config: Optional[ValidatorConfig]) -> Dict[str, Any]:
        """Get merged configuration"""
        default = self.default_config
        if config and config.config:
            default.update(config.config)
        return default


__all__ = [
    "ResourceFileSizeValidator",
]
