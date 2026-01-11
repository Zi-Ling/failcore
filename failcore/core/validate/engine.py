# failcore/core/validate/engine.py
"""
Validation Engine: Orchestration layer for validation execution.

The engine is responsible for:
- Loading and applying policy
- Selecting enabled builtin
- Executing builtin in priority order
- Short-circuiting on BLOCK (in strict mode)
- Aggregating decisions
- Applying enforcement mode (shadow/warn/block)
- Handling overrides and exceptions

The engine does NOT contain validation logic itself.
It only orchestrates builtin registered in the registry.
"""

from __future__ import annotations

from typing import Dict, List, Optional
import os
from datetime import datetime

from .contracts import (
    Context,
    Decision,
    DecisionOutcome,
    Policy,
    ValidatorConfig,
    EnforcementMode,
)
from .validator import BaseValidator


class ValidationEngine:
    """
    Validation orchestration engine.
    
    The engine executes builtin according to policy configuration.
    
    Key responsibilities:
    - Load policy
    - Select enabled builtin
    - Execute in priority order
    - Apply enforcement mode
    - Handle overrides and exceptions
    - Aggregate decisions
    """
    
    # Recommended execution order by domain
    DOMAIN_PRIORITY = {
        "contract": 10,  # Contract validation first
        "type": 20,      # Type validation second
        "security": 30,  # Security checks third
        "network": 40,   # Network checks fourth
        "resource": 50,  # Resource checks last
    }
    
    def __init__(
        self,
        policy: Optional[Policy] = None,
        registry: Optional["ValidatorRegistry"] = None,
        strict_mode: bool = False,
    ):
        """
        Initialize validation engine.
        
        Args:
            policy: Validation policy (if None, uses permissive defaults)
            registry: Validator registry (if None, uses global registry)
            strict_mode: If True, short-circuit on first BLOCK decision
        """
        self.policy = policy or Policy()
        self.registry = registry
        self.strict_mode = strict_mode
    
    def evaluate(
        self,
        context: Context,
        validators: Optional[List[BaseValidator]] = None,
    ) -> List[Decision]:
        """
        Execute validation and return all decisions.
        
        Args:
            context: Validation context
            validators: Optional list of builtin to run
                       (if None, uses all enabled builtin from policy)
        
        Returns:
            List of decisions (ordered by execution)
        
        Notes:
        - In strict mode, stops on first BLOCK decision
        - In shadow mode, converts all BLOCK to WARN
        - Applies overrides and exceptions
        """
        # Get builtin to execute
        if validators is None:
            validators = self._get_validators_to_execute()
        
        # Sort by priority
        validators = self._sort_validators(validators)
        
        # Execute builtin
        decisions: List[Decision] = []
        
        for validator in validators:
            # Get validator configuration from policy
            config = self.policy.get_validator_config(validator.id)
            
            # Skip if disabled
            if config and not config.enabled:
                continue
            
            # Check exceptions
            if config and self._has_active_exception(validator.id, context, config):
                # Exception active: add ALLOW decision with evidence
                decisions.append(
                    Decision.allow(
                        code=f"FC_EXCEPTION_{validator.id.upper()}",
                        validator_id=validator.id,
                        message=f"Validation bypassed due to active exception",
                        evidence={"reason": "exception_active"},
                    )
                )
                continue
            
            # Execute validator
            try:
                validator_decisions = validator.evaluate(context, config)
            except Exception as e:
                # Validator error: create error decision
                validator_decisions = [
                    Decision.block(
                        code=f"FC_ENGINE_VALIDATOR_ERROR",
                        validator_id=validator.id,
                        message=f"Validator error: {e}",
                        evidence={"error": str(e), "validator": validator.id},
                    )
                ]
            
            # Apply enforcement mode
            for decision in validator_decisions:
                decision = self._apply_enforcement_mode(decision, config)
                decision = self._apply_override(decision, config)
                decisions.append(decision)
            
            # Short-circuit on BLOCK (strict mode only)
            if self.strict_mode:
                blocking = [d for d in validator_decisions if d.is_blocking]
                if blocking:
                    break
        
        return decisions
    
    def evaluate_and_raise(
        self,
        context: Context,
        validators: Optional[List[BaseValidator]] = None,
    ) -> List[Decision]:
        """
        Execute validation and raise exception if blocked.
        
        Args:
            context: Validation context
            validators: Optional list of builtin to run
        
        Returns:
            List of decisions
        
        Raises:
            ValidationBlockedError: If any BLOCK decisions are found
        """
        decisions = self.evaluate(context, validators)
        
        # Check for blocking decisions
        blocking = [d for d in decisions if d.is_blocking]
        if blocking:
            raise ValidationBlockedError(
                f"Validation blocked: {blocking[0].message}",
                decisions=blocking,
                all_decisions=decisions,
            )
        
        return decisions
    
    def _get_validators_to_execute(self) -> List[BaseValidator]:
        """Get list of enabled builtin from registry"""
        if not self.registry:
            return []
        
        # Get all builtin from registry
        all_validators = self.registry.list_validators()
        
        # Filter by policy
        enabled_ids = {
            v.id for v in self.policy.get_enabled_validators()
        }
        
        # If policy is empty, enable all builtin
        if not enabled_ids:
            return all_validators
        
        return [v for v in all_validators if v.id in enabled_ids]
    
    def _sort_validators(self, validators: List[BaseValidator]) -> List[BaseValidator]:
        """
        Sort builtin by priority.
        
        Priority rules:
        1. Explicit priority from policy config
        2. Domain priority (contract → type → security → network → resource)
        3. Validator ID (alphabetical)
        """
        def get_priority(validator: BaseValidator) -> tuple:
            # Get explicit priority from policy
            config = self.policy.get_validator_config(validator.id)
            explicit_priority = config.priority if config else 100
            
            # Get domain priority
            domain_priority = self.DOMAIN_PRIORITY.get(validator.domain, 100)
            
            return (explicit_priority, domain_priority, validator.id)
        
        return sorted(validators, key=get_priority)
    
    def _apply_enforcement_mode(
        self,
        decision: Decision,
        config: Optional[ValidatorConfig]
    ) -> Decision:
        """
        Apply enforcement mode to decision.
        
        - SHADOW: Convert BLOCK → WARN
        - WARN: Convert BLOCK → WARN
        - BLOCK: No change
        """
        if not config:
            return decision
        
        mode = config.enforcement
        
        if mode == EnforcementMode.SHADOW and decision.is_blocking:
            # Shadow mode: observe only
            decision.decision = DecisionOutcome.WARN
            decision.evidence["enforcement_mode"] = "shadow"
            decision.evidence["original_decision"] = "block"
            decision.message = f"[SHADOW] {decision.message}"
        
        elif mode == EnforcementMode.WARN and decision.is_blocking:
            # Warn mode: warn but don't block
            decision.decision = DecisionOutcome.WARN
            decision.evidence["enforcement_mode"] = "warn"
            decision.evidence["original_decision"] = "block"
        
        return decision
    
    def _apply_override(
        self,
        decision: Decision,
        config: Optional[ValidatorConfig]
    ) -> Decision:
        """
        Apply override if configured.
        
        Checks:
        1. Is override enabled for this validator?
        2. Is global override enabled?
        3. Is override token valid?
        4. Is override expired?
        
        If override is active, convert BLOCK → ALLOW with evidence.
        """
        if not decision.is_blocking:
            return decision
        
        # Check if override is allowed for this validator
        if config and not config.allow_override:
            return decision
        
        # Check global override
        if not self.policy.global_override.enabled:
            return decision
        
        # Check override token
        if self.policy.global_override.require_token:
            token_var = self.policy.global_override.token_env_var
            token = os.environ.get(token_var)
            if not token:
                return decision
        
        # Check expiration
        if self.policy.global_override.expires_at:
            try:
                expiry = datetime.fromisoformat(
                    self.policy.global_override.expires_at.replace('Z', '+00:00')
                )
                if datetime.now(expiry.tzinfo) > expiry:
                    return decision
            except Exception:
                return decision
        
        # Override is active: convert to ALLOW
        decision.decision = DecisionOutcome.ALLOW
        decision.evidence["override_active"] = True
        decision.evidence["override_reason"] = "emergency_override"
        decision.evidence["original_decision"] = "block"
        decision.overrideable = True
        decision.message = f"[OVERRIDE] {decision.message}"
        
        return decision
    
    def _has_active_exception(
        self,
        validator_id: str,
        context: Context,
        config: ValidatorConfig
    ) -> bool:
        """
        Check if there's an active exception for this validator.
        
        Returns True if an exception is active and not expired.
        """
        for exception in config.exceptions:
            # Check expiration
            if exception.is_expired():
                continue
            
            # Check scope match
            if exception.scope:
                # Match tool
                if "tool" in exception.scope:
                    if context.tool != exception.scope["tool"]:
                        continue
                
                # Match param
                if "param" in exception.scope:
                    param_name = exception.scope["param"]
                    if param_name not in context.params:
                        continue
            
            # Exception matches
            return True
        
        return False


class ValidationBlockedError(Exception):
    """
    Exception raised when validation blocks execution.
    
    Contains all blocking decisions and the full decision list.
    """
    
    def __init__(
        self,
        message: str,
        decisions: List[Decision],
        all_decisions: Optional[List[Decision]] = None
    ):
        super().__init__(message)
        self.decisions = decisions
        self.all_decisions = all_decisions or decisions


__all__ = [
    "ValidationEngine",
    "ValidationBlockedError",
]
