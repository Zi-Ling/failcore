# failcore/core/validate/builtin/output/contract.py
"""
Output Contract Validator - Bridge to failcore.core.contract

This validator checks tool output against expected contracts (kind, schema).
This is a standard BaseValidator implementation that returns Decision objects.

Note: This file is named "contract.py" to distinguish it from:
- contracts/ directory: Validation contracts (Policy/Context/Decision)
- contract/ module: Contract checking logic (ExpectedKind, check_output)
- contract validator: This validator implementation
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from failcore.core.validate.validator import BaseValidator
from failcore.core.validate.contracts import Context, Decision, ValidatorConfig, DecisionOutcome, RiskLevel
from failcore.core.contract import ExpectedKind, check_output, ContractResult


class OutputContractValidator(BaseValidator):
    """
    Output Contract Validator
    
    Validates tool output against expected contract (kind, JSON Schema).
    Returns Decision objects (allow/warn/block) based on contract compliance.
    """
    
    @property
    def id(self) -> str:
        return "output_contract"
    
    @property
    def domain(self) -> str:
        return "contract"
    
    @property
    def config_schema(self) -> Optional[Dict[str, Any]]:
        """
        JSON schema for validator configuration.
        
        schema: JSON Schema (Draft 7 compatible subset)
          - Supports: type, properties, required, items, enum
          - Example: {"type": "object", "properties": {"id": {"type": "string"}}}
        expected_kind: Expected output kind (JSON, TEXT, etc.)
        """
        return {
            "type": "object",
            "properties": {
                "expected_kind": {
                    "type": "string",
                    "enum": ["JSON", "TEXT", "BINARY"],
                    "description": "Expected output kind",
                },
                "schema": {
                    "type": "object",
                    "description": "JSON Schema (Draft 7 compatible subset: type, properties, required, items, enum)",
                },
            },
        }
    
    @property
    def default_config(self) -> Dict[str, Any]:
        """Default configuration"""
        return {
            "expected_kind": None,
            "schema": None,
        }
    
    def evaluate(
        self,
        context: Context,
        config: Optional[ValidatorConfig] = None,
    ) -> List[Decision]:
        """
        Evaluate output contract validation
        
        Args:
            context: Validation context (must contain result field)
            config: Validator configuration (expected_kind, schema)
            
        Returns:
            List of Decision objects (empty if contract satisfied)
            
        Notes:
            - Returns ALLOW decision if contract satisfied
            - Returns WARN decision if contract drift detected
            - Returns BLOCK decision if contract violation detected
            - Evidence is minimized (no raw_excerpt, only types/errors)
        """
        decisions: List[Decision] = []
        
        # Get configuration
        cfg = self._get_config(config)
        expected_kind_str = cfg.get("expected_kind")
        schema = cfg.get("schema")
        
        # Parse expected_kind
        expected_kind = None
        if expected_kind_str:
            try:
                expected_kind = ExpectedKind(expected_kind_str)
            except ValueError:
                # Invalid kind - create error decision
                return [
                    Decision.block(
                        code="FC_OUTPUT_CONTRACT_INVALID_CONFIG",
                        validator_id=self.id,
                        message=f"Invalid expected_kind: {expected_kind_str}",
                        evidence={
                            "config_error": "invalid_expected_kind",
                            "provided_kind": expected_kind_str,
                            "valid_kinds": ["JSON", "TEXT", "BINARY"],
                        },
                    )
                ]
        
        # Check if result is present
        if context.result is None:
            # No result - skip validation (not an error)
            return []
        
        # Use contract checker
        contract_result: ContractResult = check_output(
            value=context.result,
            expected_kind=expected_kind,
            schema=schema,
            strict_mode=False,  # Enforcement is handled by engine, not validator
        )
        
        # Build evidence (minimized - no raw_excerpt)
        evidence: Dict[str, Any] = {
            "contract_check": True,
            "schema_used": schema is not None,
        }
        
        if expected_kind:
            evidence["expected_kind"] = expected_kind.value
        if schema:
            # Only record schema keys (not full schema)
            if isinstance(schema, dict):
                evidence["schema_keys"] = list(schema.keys())
        
        # Convert ContractResult to Decision
        if contract_result.is_ok():
            # Contract satisfied - return ALLOW decision
            decisions.append(
                Decision.allow(
                    code="FC_OUTPUT_CONTRACT_OK",
                    validator_id=self.id,
                    message="Output contract satisfied",
                    evidence=evidence,
                    tool=context.tool,
                    step_id=context.step_id,
                )
            )
            return decisions
        
        # Contract violation/drift detected
        drift_type = contract_result.drift_type.value if contract_result.drift_type else "UNKNOWN"
        observed_kind = contract_result.observed_kind
        
        # Add drift information to evidence (minimized)
        evidence.update({
            "drift_type": drift_type,
            "observed_kind": observed_kind,
            "reason": contract_result.reason,
        })
        
        if contract_result.fields_missing:
            # Only record field names, not values
            evidence["fields_missing"] = contract_result.fields_missing
        if contract_result.parse_error:
            # Only record error type and truncated message (minimize evidence)
            # parse_error is Optional[str] in ContractResult
            error_msg = contract_result.parse_error
            evidence["parse_error_type"] = "JSONDecodeError" if "JSON" in error_msg else "ParseError"
            # Truncate error message to 100 chars (minimize evidence size)
            if len(error_msg) > 100:
                evidence["parse_error_preview"] = error_msg[:100] + "..."
            else:
                evidence["parse_error_preview"] = error_msg
        
        # Determine code and rule_id based on drift type
        # Note: Code naming follows FC_{DOMAIN}_{CATEGORY}_{SPECIFIC} convention
        # DriftType enum values are lowercase (e.g., "output_kind_mismatch")
        if drift_type == "output_kind_mismatch":
            code = "FC_OUTPUT_CONTRACT_TYPE_MISMATCH"
            rule_id = "type_mismatch"
        elif drift_type == "invalid_json":
            code = "FC_OUTPUT_CONTRACT_INVALID_JSON"
            rule_id = "invalid_json"
        elif drift_type == "missing_required_fields":
            code = "FC_OUTPUT_CONTRACT_MISSING_FIELDS"
            rule_id = "missing_fields"
        elif drift_type == "schema_mismatch":
            code = "FC_OUTPUT_CONTRACT_SCHEMA_MISMATCH"
            rule_id = "schema_mismatch"
        else:
            code = "FC_OUTPUT_CONTRACT_VIOLATION"
            rule_id = "contract_violation"
        
        # Map contract decision to validation decision
        # Note: Enforcement mode (warn vs block) is handled by engine, not validator
        # Validator always returns WARN for drift (engine can elevate to BLOCK based on enforcement mode)
        decision_outcome = DecisionOutcome.WARN
        
        # Create decision
        decisions.append(
            Decision(
                decision=decision_outcome,
                code=code,
                validator_id=self.id,
                rule_id=rule_id,
                message=f"Contract {drift_type.lower().replace('_', ' ')}: {contract_result.reason}",
                evidence=evidence,
                risk_level=RiskLevel.MEDIUM,
                tool=context.tool,
                step_id=context.step_id,
            )
        )
        
        return decisions
    
    def _get_config(self, config: Optional[ValidatorConfig]) -> Dict[str, Any]:
        """Get merged configuration"""
        default = self.default_config
        if config and config.config:
            default.update(config.config)
        return default


__all__ = [
    "OutputContractValidator",
]
