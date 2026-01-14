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
from datetime import datetime

from .contracts import (
    Context,
    Decision,
    DecisionOutcome,
    Policy,
    ValidatorConfig,
    EnforcementMode,
)
from .constants import MetaKeys
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
        registry: "ValidatorRegistry",
        policy: Optional[Policy] = None,
        strict_mode: bool = False,
    ):
        """
        Initialize validation engine.
        
        Args:
            policy: Validation policy (if None, uses permissive defaults)
            registry: Validator registry (required, no global registry)
            strict_mode: If True, short-circuit on first BLOCK decision
        """
        if registry is None:
            raise ValueError("registry parameter is required (no global registry)")
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
            
            # Defensive check: ensure all required validators are registered (fail-fast)
            # This prevents users from bypassing factory functions (create_default_engine)
            if self.policy and self.policy.validators:
                from .bootstrap import ensure_registered
                ensure_registered(self.registry, self.policy)
        
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
                decision = self._apply_override(decision, config, context)
                decisions.append(decision)
            
            # Short-circuit on BLOCK (strict mode only)
            if self.strict_mode:
                blocking = [d for d in validator_decisions if d.is_blocking]
                if blocking:
                    break
        
        # Deduplicate decisions (merge duplicates from multiple validators)
        from .deduplication import deduplicate_decisions
        decisions = deduplicate_decisions(decisions)
        
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
        # Registry is required (enforced in __init__)
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
        
        Enforcement mode from policy:
        - SHADOW: Convert BLOCK → WARN (observe only)
        - WARN: Convert BLOCK → WARN (warn but don't block)
        - BLOCK: No change (enforce blocking)
        
        Strict mode override (runtime execution mode):
        - strict=True: Elevate all WARN/SHADOW → BLOCK
        - strict=False: Lower BLOCK → WARN (if config allows)
        
        Note: Strict mode does NOT modify the policy object, only affects
        the decision at execution time.
        """
        if not config:
            return decision
        
        mode = config.enforcement
        
        # First, apply policy-defined enforcement mode
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
        
        # Then, apply strict mode override (runtime execution mode)
        # Strict mode: elevate WARN/SHADOW → BLOCK
        if self.strict_mode:
            if decision.decision == DecisionOutcome.WARN:
                original_mode = decision.evidence.get("enforcement_mode", "warn")
                decision.decision = DecisionOutcome.BLOCK
                decision.evidence["strict_mode_override"] = True
                decision.evidence["enforcement_mode"] = f"{original_mode}_elevated_by_strict"
                decision.evidence["original_decision"] = original_mode
                decision.message = f"[STRICT] {decision.message}"
        
        # Non-strict mode: lower BLOCK → WARN (only if config allows)
        elif not self.strict_mode:
            if decision.is_blocking and mode in (EnforcementMode.WARN, EnforcementMode.SHADOW):
                # Already handled above, but if somehow we have a BLOCK
                # with WARN/SHADOW enforcement, lower it
                decision.decision = DecisionOutcome.WARN
                decision.evidence["strict_mode_override"] = True
                decision.evidence["enforcement_mode"] = f"{mode.value}_enforced"
                decision.evidence["original_decision"] = "block"
        
        return decision
    
    def _apply_override(
        self,
        decision: Decision,
        config: Optional[ValidatorConfig],
        context: Context,
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
        
        # Fail-closed: if enabled but expires_at is None, reject override
        if not self.policy.global_override.expires_at:
            # Log violation but don't block (evidence is logged)
            decision.evidence["override_rejected"] = True
            decision.evidence["override_rejection_reason"] = "expires_at_required_when_enabled"
            decision.evidence["override_config"] = {
                "enabled": True,
                "expires_at": None,
                "error": "Global override enabled but expires_at is not set. Override rejected for safety."
            }
            return decision  # Return original decision (block)
        
        # Get current time from context metadata (injected by caller)
        # For core extraction: timestamp must be provided in context.metadata
        current_time = None
        if hasattr(context, 'metadata') and context.metadata:
            timestamp_str = context.metadata.get(MetaKeys.TIMESTAMP)
            if timestamp_str:
                try:
                    current_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except Exception:
                    # Parse error: reject override (fail-closed)
                    decision.evidence["override_rejected"] = True
                    decision.evidence["override_rejection_reason"] = "timestamp_parse_error"
                    return decision
        
        # Check override token
        override_token = None
        if self.policy.global_override.require_token:
            # Get token from context metadata (injected by caller)
            # For core extraction: override_token must be provided in context.metadata
            if hasattr(context, 'metadata') and context.metadata:
                override_token = context.metadata.get(MetaKeys.OVERRIDE_TOKEN)
            if not override_token:
                # No token provided: reject override (fail-closed)
                decision.evidence["override_rejected"] = True
                decision.evidence["override_rejection_reason"] = "override_token_missing"
                return decision
        
        # Check expiration (fail-closed: if parse fails, reject)
        try:
            expiry_str = self.policy.global_override.expires_at.replace('Z', '+00:00')
            expiry = datetime.fromisoformat(expiry_str)
            
            # Check if timezone is present
            if expiry.tzinfo is None:
                decision.evidence["override_rejected"] = True
                decision.evidence["override_rejection_reason"] = "expires_at_missing_timezone"
                return decision
            
            # For core extraction: current_time must be provided in context.metadata
            if current_time is None:
                decision.evidence["override_rejected"] = True
                decision.evidence["override_rejection_reason"] = "timestamp_missing"
                return decision
            
            # Ensure current_time has timezone if expiry has timezone
            if expiry.tzinfo and current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=expiry.tzinfo)
            
            # Check if expired
            if current_time > expiry:
                # Override expired: reject
                decision.evidence["override_rejected"] = True
                decision.evidence["override_rejection_reason"] = "expired"
                decision.evidence["override_expired_at"] = self.policy.global_override.expires_at
                return decision
        except Exception as e:
            # Parse error: reject override (fail-closed)
            decision.evidence["override_rejected"] = True
            decision.evidence["override_rejection_reason"] = "expires_at_parse_error"
            decision.evidence["override_parse_error"] = str(e)
            return decision
        
        # Override is active: convert to ALLOW
        decision.decision = DecisionOutcome.ALLOW
        decision.evidence["override_active"] = True
        decision.evidence["override_reason"] = "emergency_override"
        decision.evidence["override_expires_at"] = self.policy.global_override.expires_at
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
        # Get current time from context metadata (injected by caller)
        # For core extraction: timestamp must be provided in context.metadata
        current_time = None
        if hasattr(context, 'metadata') and context.metadata:
            timestamp_str = context.metadata.get(MetaKeys.TIMESTAMP)
            if timestamp_str:
                try:
                    current_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except Exception:
                    # Parse error: treat as expired (fail-closed)
                    return False
        
        for exception in config.exceptions:
            # Check expiration (pass current_time if available)
            # If current_time is None, exception.is_expired will treat as expired (fail-closed)
            if exception.is_expired(current_time):
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
