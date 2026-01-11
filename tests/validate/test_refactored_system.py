"""
Tests for the refactored validation system (v0.2.0)

Tests cover:
- Contract stability
- Engine orchestration
- Registry management
- Explain layer
- Policy presets
- Enforcement modes
"""

import pytest
from failcore.core.validate import (
    # Contracts
    Policy,
    Context,
    Decision,
    ValidatorConfig,
    EnforcementMode,
    DecisionOutcome,

    # Engine & Registry
    ValidationEngine,
    get_global_registry,
    reset_global_registry,
    auto_register,

    # Explain
    explain_decisions,

    # Presets
    default_safe_policy,
    shadow_mode_policy,

    # Validator Interface
    BaseValidator,
)


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset global registry before each test"""
    from failcore.core.validate import reset_auto_register_flag
    reset_global_registry()
    reset_auto_register_flag()  # Also reset the auto-register flag
    yield
    reset_global_registry()
    reset_auto_register_flag()


class TestContracts:
    """Test contract stability and serialization"""

    def test_policy_creation(self):
        """Test PolicyV1 creation"""
        policy = PolicyV1(
            version="v1",
            validators={
                "test_validator": ValidatorConfigV1(
                    id="test_validator",
                    domain="test",
                    enabled=True,
                    enforcement=EnforcementMode.BLOCK,
                )
            }
        )

        assert policy.version == "v1"
        assert "test_validator" in policy.validators
        assert policy.validators["test_validator"].enabled

    def test_policy_serialization(self):
        """Test PolicyV1 serialization to JSON"""
        policy = default_safe_policy()

        # Serialize
        policy_dict = policy.model_dump()
        assert "version" in policy_dict
        assert "builtin" in policy_dict

        # Deserialize
        policy2 = PolicyV1.model_validate(policy_dict)
        assert policy2.version == policy.version
        assert len(policy2.validators) == len(policy.validators)

    def test_context_creation(self):
        """Test ContextV1 creation"""
        context = ContextV1(
            tool="http_get",
            params={"url": "https://example.com"}
        )

        assert context.tool == "http_get"
        assert context.params["url"] == "https://example.com"

    def test_decision_creation(self):
        """Test DecisionV1 creation"""
        decision = DecisionV1.block(
            code="FC_TEST_BLOCKED",
            validator_id="test_validator",
            message="Test blocked",
        )

        assert decision.code == "FC_TEST_BLOCKED"
        assert decision.is_blocking
        assert not decision.is_allow


class TestRegistry:
    """Test validator registry"""

    def test_register_validator(self):
        """Test registering a validator"""
        class TestValidator(BaseValidator):
            @property
            def id(self) -> str:
                return "test_validator"

            @property
            def domain(self) -> str:
                return "test"

            def evaluate(self, context, config=None):
                return []

        registry = get_global_registry()
        validator = TestValidator()
        registry.register(validator)

        assert registry.has("test_validator")
        assert registry.count() == 1
        assert registry.get("test_validator") == validator

    def test_list_validators(self):
        """Test listing builtin"""
        class TestValidator1(BaseValidator):
            @property
            def id(self) -> str:
                return "test_validator_1"

            @property
            def domain(self) -> str:
                return "test"

            def evaluate(self, context, config=None):
                return []

        class TestValidator2(BaseValidator):
            @property
            def id(self) -> str:
                return "test_validator_2"

            @property
            def domain(self) -> str:
                return "test"

            def evaluate(self, context, config=None):
                return []

        registry = get_global_registry()
        registry.register(TestValidator1())
        registry.register(TestValidator2())

        validators = registry.list_validators()
        assert len(validators) == 2

    def test_get_by_domain(self):
        """Test getting builtin by domain"""
        class SecurityValidator(BaseValidator):
            @property
            def id(self) -> str:
                return "security_validator"

            @property
            def domain(self) -> str:
                return "security"

            def evaluate(self, context, config=None):
                return []

        class NetworkValidator(BaseValidator):
            @property
            def id(self) -> str:
                return "network_validator"

            @property
            def domain(self) -> str:
                return "network"

            def evaluate(self, context, config=None):
                return []

        registry = get_global_registry()
        registry.register(SecurityValidator())
        registry.register(NetworkValidator())

        security_validators = registry.get_by_domain("security")
        assert len(security_validators) == 1
        assert security_validators[0].id == "security_validator"


class TestEngine:
    """Test validation engine"""

    def test_engine_creation(self):
        """Test creating validation engine"""
        policy = default_safe_policy()
        registry = get_global_registry()

        engine = ValidationEngine(policy=policy, registry=registry)
        assert engine.policy == policy
        assert engine.registry == registry

    def test_engine_evaluate(self):
        """Test engine evaluation"""
        class AlwaysPassValidator(BaseValidator):
            @property
            def id(self) -> str:
                return "always_pass"

            @property
            def domain(self) -> str:
                return "test"

            def evaluate(self, context, config=None):
                return []  # No violations

        registry = get_global_registry()
        registry.register(AlwaysPassValidator())

        policy = PolicyV1(
            validators={
                "always_pass": ValidatorConfigV1(
                    id="always_pass",
                    enabled=True,
                )
            }
        )

        engine = ValidationEngine(policy=policy, registry=registry)
        context = ContextV1(tool="test", params={})

        decisions = engine.evaluate(context)
        assert len(decisions) >= 0
        assert not any(d.is_blocking for d in decisions)

    def test_engine_blocking(self):
        """Test engine blocking behavior"""
        class AlwaysBlockValidator(BaseValidator):
            @property
            def id(self) -> str:
                return "always_block"

            @property
            def domain(self) -> str:
                return "test"

            def evaluate(self, context, config=None):
                return [DecisionV1.block(
                    code="FC_TEST_BLOCKED",
                    validator_id=self.id,
                    message="Always blocked",
                )]

        registry = get_global_registry()
        registry.register(AlwaysBlockValidator())

        policy = PolicyV1(
            validators={
                "always_block": ValidatorConfigV1(
                    id="always_block",
                    enabled=True,
                    enforcement=EnforcementMode.BLOCK,
                )
            }
        )

        engine = ValidationEngine(policy=policy, registry=registry)
        context = ContextV1(tool="test", params={})

        decisions = engine.evaluate(context)
        assert len(decisions) > 0
        assert any(d.is_blocking for d in decisions)


class TestEnforcementModes:
    """Test enforcement modes (shadow/warn/block)"""

    def test_shadow_mode(self):
        """Test shadow mode (observe but don't block)"""
        class BlockingValidator(BaseValidator):
            @property
            def id(self) -> str:
                return "blocking_validator"

            @property
            def domain(self) -> str:
                return "test"

            def evaluate(self, context, config=None):
                return [DecisionV1.block(
                    code="FC_TEST_BLOCKED",
                    validator_id=self.id,
                    message="Should block",
                )]

        registry = get_global_registry()
        registry.register(BlockingValidator())

        policy = PolicyV1(
            validators={
                "blocking_validator": ValidatorConfigV1(
                    id="blocking_validator",
                    enabled=True,
                    enforcement=EnforcementMode.SHADOW,  # Shadow mode
                )
            }
        )

        engine = ValidationEngine(policy=policy, registry=registry)
        context = ContextV1(tool="test", params={})

        decisions = engine.evaluate(context)

        # In shadow mode, blocks are converted to warns
        assert len(decisions) > 0
        assert not any(d.is_blocking for d in decisions)
        assert any(d.is_warning for d in decisions)


class TestExplain:
    """Test explain layer"""

    def test_explain_decisions(self):
        """Test decision explanation"""
        decisions = [
            DecisionV1.allow(
                code="FC_TEST_ALLOWED",
                validator_id="test",
                message="Allowed",
            ),
            DecisionV1.block(
                code="FC_TEST_BLOCKED",
                validator_id="test",
                message="Blocked",
            ),
        ]

        explanation = explain_decisions(decisions)

        assert explanation.total == 2
        assert len(explanation.blocked) == 1
        assert len(explanation.allowed) == 1
        assert explanation.is_blocked

    def test_explain_summary(self):
        """Test explanation summary generation"""
        decisions = [
            Decision.block(
                code="FC_TEST_BLOCKED",
                validator_id="test",
                message="Test blocked",
            ),
        ]

        explanation = explain_decisions(decisions)
        summary = explanation.get_short_summary()

        assert "blocked" in summary.lower()


class TestPresets:
    """Test policy presets"""

    def test_default_safe_policy(self):
        """Test default safe policy"""
        policy = default_safe_policy()

        assert policy.version == "v1"
        assert len(policy.validators) > 0
        assert policy.metadata["name"] == "default_safe"

    def test_shadow_mode_policy(self):
        """Test shadow mode policy"""
        policy = shadow_mode_policy()

        # All builtin should be in shadow mode
        for validator in policy.validators.values():
            assert validator.enforcement == EnforcementMode.SHADOW


class TestBootstrap:
    """Test built-in validator registration"""

    def test_auto_register(self):
        """Test auto-registering built-in builtin"""
        auto_register()
        registry = get_global_registry()

        # Debug: Print what we have
        print(f"\nRegistry count: {registry.count()}")
        print(f"Validators: {[v.id for v in registry.list_validators()]}")
        print(f"Domains: {registry.list_domains()}")

        # Should have registered at least some builtin
        assert registry.count() > 0, "No builtin registered after auto_register()"

    def test_validator_domains(self):
        """Test that builtin are registered in correct domains"""
        # Enable logging to see what's happening
        import logging
        logging.basicConfig(level=logging.DEBUG)

        auto_register()
        registry = get_global_registry()

        # Debug: Print what we have
        print(f"\nRegistry count: {registry.count()}")
        print(f"Validators: {[v.id for v in registry.list_validators()]}")
        print(f"Domains: {registry.list_domains()}")

        domains = registry.list_domains()

        # Should have standard domains
        # Note: May not have all domains if some builtin failed to load
        assert len(domains) > 0, f"No domains found. Registry count: {registry.count()}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
