# tests/integration/test_contract_integration.py
"""
Contract Layer Integration Tests

Tests P0, P1, P2 functionality as defined in the implementation plan.
"""

import pytest
from failcore.core.validate import (
    ValidatorRegistry,
    ValidationResult,
    json_output_postcondition,
    output_contract_postcondition,
)
from failcore.core.contract import ExpectedKind


class TestP0CoreFunctionality:
    """P0: Core contract functionality (must pass)"""
    
    def test_contract_drift_warn_mode(self):
        """
        用例 1: Contract Drift (WARN 模式)
        
        验证最常见路径：
        - 输出是 TEXT 但期望 JSON
        - strict_mode=False → WARN
        - Step 继续执行但有警告
        """
        # Setup
        registry = ValidatorRegistry()
        registry.register_postcondition(
            "fetch_user_data",
            json_output_postcondition(strict_mode=False)
        )
        
        # Simulate tool output (TEXT instead of JSON)
        output = "Here is the user data you requested: {success: true}"
        
        context = {
            "tool": "fetch_user_data",
            "params": {"user_id": "123"},
            "result": output,
            "step_id": "s0001",
        }
        
        # Execute validation
        results = registry.validate_postconditions(
            "fetch_user_data",
            context,
            mode="fail_fast"
        )
        
        # Assertions
        assert len(results) == 1
        result = results[0]
        
        # ✅ Severity is WARN
        assert result.severity == "warn"
        
        # ✅ valid=True (non-blocking)
        assert result.valid == True
        
        # ✅ Code indicates drift
        assert result.code == "OUTPUT_KIND_MISMATCH"
        
        # ✅ Details contain drift info
        assert result.details["drift_type"] == "output_kind_mismatch"
        assert result.details["expected_kind"] == "json"
        assert result.details["observed_kind"] == "text"
        assert result.details["reason"] is not None
        
        # ✅ Message is descriptive
        assert "drift" in result.message.lower()
        
        print("✅ P0 用例 1: WARN 模式通过")
    
    def test_contract_drift_block_mode(self):
        """
        用例 2: Contract Drift (BLOCK 模式)
        
        验证 strict_mode：
        - 相同的输出
        - strict_mode=True → BLOCK
        - Step 被中止
        """
        # Setup
        registry = ValidatorRegistry()
        registry.register_postcondition(
            "fetch_user_data",
            json_output_postcondition(strict_mode=True)
        )
        
        # Same output as test 1
        output = "Here is the user data you requested: {success: true}"
        
        context = {
            "tool": "fetch_user_data",
            "params": {"user_id": "123"},
            "result": output,
            "step_id": "s0001",
        }
        
        # Execute validation
        results = registry.validate_postconditions(
            "fetch_user_data",
            context,
            mode="fail_fast"
        )
        
        # Assertions
        assert len(results) == 1
        result = results[0]
        
        # ✅ Severity is BLOCK
        assert result.severity == "block"
        
        # ✅ valid=False (blocking)
        assert result.valid == False
        
        # ✅ Code indicates violation
        assert result.code == "OUTPUT_KIND_MISMATCH"
        
        # ✅ Message indicates violation
        assert "violation" in result.message.lower()
        
        print("✅ P0 用例 2: BLOCK 模式通过")
    
    def test_valid_json_passes(self):
        """
        验证正常情况：输出是有效 JSON
        """
        registry = ValidatorRegistry()
        registry.register_postcondition(
            "fetch_user_data",
            json_output_postcondition(strict_mode=False)
        )
        
        # Valid JSON output
        output = {"user_id": "123", "name": "Alice"}
        
        context = {
            "tool": "fetch_user_data",
            "result": output,
        }
        
        results = registry.validate_postconditions(
            "fetch_user_data",
            context
        )
        
        assert len(results) == 1
        result = results[0]
        
        # ✅ No drift
        assert result.severity == "ok"
        assert result.valid == True
        
        print("✅ P0: 有效 JSON 通过")


class TestP1BehaviorConsistency:
    """P1: Behavior consistency tests (critical)"""
    
    def test_fail_fast_behavior(self):
        """
        用例 3: fail_fast 行为
        
        验证：
        - WARN 不触发 fail_fast
        - BLOCK 触发 fail_fast 并停止后续验证
        """
        registry = ValidatorRegistry()
        
        # Register multiple builtin
        # 1. WARN validator
        registry.register_postcondition(
            "test_tool",
            json_output_postcondition(strict_mode=False)  # WARN
        )
        
        # 2. BLOCK validator (will trigger fail_fast)
        registry.register_postcondition(
            "test_tool",
            output_contract_postcondition(
                expected_kind=ExpectedKind.JSON,
                strict_mode=True  # BLOCK
            )
        )
        
        # 3. Third validator (should NOT execute due to fail_fast)
        registry.register_postcondition(
            "test_tool",
            json_output_postcondition(strict_mode=False)
        )
        
        # Invalid output
        context = {
            "tool": "test_tool",
            "result": "not json",
        }
        
        # Execute with fail_fast
        results = registry.validate_postconditions(
            "test_tool",
            context,
            mode="fail_fast"
        )
        
        # ✅ First WARN executes
        assert len(results) >= 1
        assert results[0].severity == "warn"
        
        # ✅ Second BLOCK executes and stops
        assert len(results) >= 2
        assert results[1].severity == "block"
        
        # ✅ Third validator NOT executed (fail_fast stopped)
        assert len(results) == 2  # Only 2 builtin ran
        
        print("✅ P1 用例 3: fail_fast 行为正确")
    
    def test_fail_fast_warn_does_not_stop(self):
        """
        验证 WARN 不会触发 fail_fast
        """
        registry = ValidatorRegistry()
        
        # Register two WARN builtin
        registry.register_postcondition(
            "test_tool",
            json_output_postcondition(strict_mode=False)
        )
        registry.register_postcondition(
            "test_tool",
            json_output_postcondition(strict_mode=False)
        )
        
        context = {
            "tool": "test_tool",
            "result": "not json",
        }
        
        results = registry.validate_postconditions(
            "test_tool",
            context,
            mode="fail_fast"
        )
        
        # ✅ Both builtin executed (WARN doesn't stop)
        assert len(results) == 2
        assert all(r.severity == "warn" for r in results)
        
        print("✅ P1: WARN 不触发 fail_fast")
    
    def test_tool_matching_priority(self):
        """
        用例 4: 工具名匹配优先级
        
        验证：
        1. 精确匹配优先
        2. 最长 prefix 次之
        3. 全部执行（叠加）
        """
        registry = ValidatorRegistry()
        
        # Register in mixed order
        from failcore.core.validate.validator import PostconditionValidator
        
        def make_validator(name):
            return PostconditionValidator(
                name=name,
                condition=lambda ctx: ValidationResult.success(name)
            )
        
        # 1. Prefix match (shortest)
        registry.register_postcondition(
            "api.*",
            make_validator("api_general"),
            is_prefix=True
        )
        
        # 2. Prefix match (longer)
        registry.register_postcondition(
            "api.user.*",
            make_validator("api_user_strict"),
            is_prefix=True
        )
        
        # 3. Exact match
        registry.register_postcondition(
            "api.user.create",
            make_validator("exact_validator")
        )
        
        # Get builtin
        validators = registry.get_postconditions("api.user.create")
        
        # ✅ All 3 builtin returned
        assert len(validators) == 3
        
        # ✅ Correct priority order
        names = [v.name for v in validators]
        assert names == ["exact_validator", "api_user_strict", "api_general"]
        
        # Verify execution (all should run)
        context = {"tool": "api.user.create", "result": None}
        results = registry.validate_postconditions(
            "api.user.create",
            context
        )
        
        # ✅ All executed (叠加)
        assert len(results) == 3
        
        print("✅ P1 用例 4: 匹配优先级正确")


class TestP2SchemaValidation:
    """P2: Schema validation capability"""
    
    def test_schema_missing_fields_warn(self):
        """
        用例 5a: Schema mismatch (WARN 模式)
        
        验证：
        - 缺少必需字段
        - drift_type = MISSING_REQUIRED_FIELDS
        - strict=False → WARN
        """
        registry = ValidatorRegistry()
        registry.register_postcondition(
            "create_user",
            json_output_postcondition(
                schema={"required": ["user_id", "name", "email"]},
                strict_mode=False
            )
        )
        
        # Missing "email" field
        output = {"user_id": "123", "name": "Alice"}
        
        context = {
            "tool": "create_user",
            "result": output,
        }
        
        results = registry.validate_postconditions(
            "create_user",
            context
        )
        
        assert len(results) == 1
        result = results[0]
        
        # ✅ WARN severity
        assert result.severity == "warn"
        
        # ✅ Drift type is schema mismatch
        assert result.details["drift_type"] == "missing_required_fields"
        
        # ✅ Missing fields listed
        assert result.details["fields_missing"] == ["email"]
        
        print("✅ P2 用例 5a: Schema WARN 模式通过")
    
    def test_schema_missing_fields_block(self):
        """
        用例 5b: Schema mismatch (BLOCK 模式)
        """
        registry = ValidatorRegistry()
        registry.register_postcondition(
            "create_user",
            json_output_postcondition(
                schema={"required": ["user_id", "name"]},
                strict_mode=True
            )
        )
        
        # Missing "name" field
        output = {"user_id": "123"}
        
        context = {
            "tool": "create_user",
            "result": output,
        }
        
        results = registry.validate_postconditions(
            "create_user",
            context
        )
        
        assert len(results) == 1
        result = results[0]
        
        # ✅ BLOCK severity
        assert result.severity == "block"
        assert result.valid == False
        
        print("✅ P2 用例 5b: Schema BLOCK 模式通过")
    
    def test_schema_valid_passes(self):
        """
        验证符合 schema 的输出通过
        """
        registry = ValidatorRegistry()
        registry.register_postcondition(
            "create_user",
            json_output_postcondition(
                schema={"required": ["user_id", "name"]},
                strict_mode=True
            )
        )
        
        # All required fields present
        output = {"user_id": "123", "name": "Alice", "email": "alice@example.com"}
        
        context = {
            "tool": "create_user",
            "result": output,
        }
        
        results = registry.validate_postconditions(
            "create_user",
            context
        )
        
        assert len(results) == 1
        assert results[0].severity == "ok"
        
        print("✅ P2: Schema 验证通过")


class TestContractResultTraceEvent:
    """Test ContractResult to trace event conversion"""
    
    def test_trace_event_format(self):
        """
        验证 CONTRACT_DRIFT 事件格式符合 trace schema
        """
        from failcore.core.contract import check_output, ExpectedKind
        
        # Create a drift
        result = check_output(
            value="not json",
            expected_kind=ExpectedKind.JSON,
            strict_mode=False
        )
        
        # Convert to trace event
        event_data = result.to_trace_event()
        
        # ✅ Has contract key
        assert "contract" in event_data
        
        contract = event_data["contract"]
        
        # ✅ Required fields present
        assert "drift_type" in contract
        assert "expected_kind" in contract
        assert "observed_kind" in contract
        assert "decision" in contract
        assert "reason" in contract
        
        # ✅ Values correct
        assert contract["drift_type"] == "output_kind_mismatch"
        assert contract["expected_kind"] == "json"
        assert contract["observed_kind"] == "text"
        assert contract["decision"] == "warn"
        
        print("✅ Trace 事件格式正确")


class TestValidationResultSeverity:
    """Test ValidationResult.valid derivation from severity"""
    
    def test_severity_determines_valid(self):
        """
        验证 valid 由 severity 推导，不会冲突
        """
        # OK → valid=True
        result_ok = ValidationResult.success("ok")
        assert result_ok.severity == "ok"
        assert result_ok.valid == True
        
        # WARN → valid=True (non-blocking)
        result_warn = ValidationResult.warning("drift", details={})
        assert result_warn.severity == "warn"
        assert result_warn.valid == True
        
        # BLOCK → valid=False (blocking)
        result_block = ValidationResult.failure("violation", details={})
        assert result_block.severity == "block"
        assert result_block.valid == False
        
        print("✅ valid 由 severity 正确推导")
    
    def test_cannot_create_conflicting_state(self):
        """
        验证无法创建冲突的 valid/severity 组合
        """
        # severity 是唯一的真实状态来源
        result = ValidationResult(
            message="test",
            severity="block"
        )
        
        # valid 自动推导为 False
        assert result.valid == False
        
        # 即使你试图"覆盖"valid，它仍然由 severity 决定
        # (因为 valid 是 @property)
        
        print("✅ 无法创建冲突状态")


def run_all_tests():
    """Run all tests with detailed output"""
    print("\n" + "="*70)
    print("Contract Layer Integration Tests")
    print("="*70 + "\n")
    
    # P0 Tests
    print("📦 P0: Core Functionality Tests")
    print("-"*70)
    p0 = TestP0CoreFunctionality()
    p0.test_contract_drift_warn_mode()
    p0.test_contract_drift_block_mode()
    p0.test_valid_json_passes()
    print()
    
    # P1 Tests
    print("📦 P1: Behavior Consistency Tests")
    print("-"*70)
    p1 = TestP1BehaviorConsistency()
    p1.test_fail_fast_behavior()
    p1.test_fail_fast_warn_does_not_stop()
    p1.test_tool_matching_priority()
    print()
    
    # P2 Tests
    print("📦 P2: Schema Validation Tests")
    print("-"*70)
    p2 = TestP2SchemaValidation()
    p2.test_schema_missing_fields_warn()
    p2.test_schema_missing_fields_block()
    p2.test_schema_valid_passes()
    print()
    
    # Infrastructure Tests
    print("📦 Infrastructure Tests")
    print("-"*70)
    trace_test = TestContractResultTraceEvent()
    trace_test.test_trace_event_format()
    
    severity_test = TestValidationResultSeverity()
    severity_test.test_severity_determines_valid()
    severity_test.test_cannot_create_conflicting_state()
    print()
    
    print("="*70)
    print("✅ All tests passed!")
    print("="*70)


if __name__ == "__main__":
    run_all_tests()

