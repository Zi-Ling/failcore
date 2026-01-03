"""
Test validator refactor (v0.1.2 → v0.1.3)

Ensures backward compatibility and new API work correctly.
"""

import os
import tempfile
from pathlib import Path


def test_fs_safe_basic():
    """Test basic fs_safe() unchanged"""
    from failcore.presets import fs_safe
    
    registry = fs_safe()
    assert registry is not None
    print("✅ fs_safe() basic mode works")


def test_fs_safe_strict_mode():
    """Test new fs_safe(strict=True) API"""
    from failcore.presets import fs_safe
    
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = fs_safe(strict=True, sandbox_root=tmpdir)
        assert registry is not None
        print("✅ fs_safe(strict=True) works")


def test_fs_safe_sandbox_deprecated():
    """Test deprecated fs_safe_sandbox() still works"""
    import warnings
    from failcore.presets import fs_safe_sandbox
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = fs_safe_sandbox(sandbox_root=tmpdir)
            assert registry is not None
            
            # Check deprecation warning was raised
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "fs_safe(strict=True)" in str(w[0].message)
    
    print("✅ fs_safe_sandbox() deprecated but works")


def test_security_module_import():
    """Test security validators can be imported from core"""
    from failcore.core.validate.validators.security import path_traversal_precondition
    
    checker = path_traversal_precondition("path", sandbox_root=os.getcwd())
    assert checker is not None
    print("✅ Security module import works")


def test_path_traversal_detection():
    """Test path traversal actually blocks ../ attacks"""
    from failcore.presets import fs_safe
    from failcore.core.validate.validator import ValidationContext
    
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = fs_safe(strict=True, sandbox_root=tmpdir)
        
        # Test valid path
        ctx = ValidationContext(
            tool="write_file",
            params={"path": "test.txt", "content": "data"}
        )
        results = registry.validate_preconditions(ctx.tool, ctx.to_dict())
        # validate_preconditions returns List[ValidationResult]
        # Empty list or all valid = success
        is_valid = all(r.valid for r in results) if results else True
        assert is_valid, f"Valid path rejected: {[r.message for r in results if not r.valid]}"
        
        # Test path traversal attack
        ctx = ValidationContext(
            tool="write_file",
            params={"path": "../escape.txt", "content": "hack"}
        )
        results = registry.validate_preconditions(ctx.tool, ctx.to_dict())
        # Should have at least one failure
        has_failure = any(not r.valid for r in results)
        assert has_failure, "Path traversal not blocked!"
        assert any("PATH_TRAVERSAL" in r.code for r in results if not r.valid)
        
    print("✅ Path traversal detection works")


def test_validators_module_structure():
    """Test validators module exports correctly"""
    from failcore.core.validate import validators
    
    # Check contract validators
    assert hasattr(validators, 'output_contract_postcondition')
    
    # Check security validators
    assert hasattr(validators, 'path_traversal_precondition')
    
    print("✅ Validators module structure correct")


def run_all_tests():
    """Run all refactor tests"""
    print("\n" + "=" * 60)
    print("Testing Validator Refactor (v0.1.2 → v0.1.3)")
    print("=" * 60 + "\n")
    
    tests = [
        test_fs_safe_basic,
        test_fs_safe_strict_mode,
        test_fs_safe_sandbox_deprecated,
        test_security_module_import,
        test_path_traversal_detection,
        test_validators_module_structure,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)

