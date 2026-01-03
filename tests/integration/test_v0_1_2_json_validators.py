#!/usr/bin/env python3
"""
Test script for new validators (v0.1.3)

Tests:
1. Type validators
2. Network validators (SSRF prevention)
3. Resource validators
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from failcore import Session, presets
from failcore.core.tools.registry import ToolRegistry


def create_test_tools():
    """Create test tools for demonstration"""
    registry = ToolRegistry()
    
    # File read tool
    def read_file(path: str) -> str:
        """Read file from disk"""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    
    registry.register("read_file", read_file)
    
    # File write tool
    def write_file(path: str, content: str) -> str:
        """Write file to disk"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {len(content)} bytes to {path}"
    
    registry.register("write_file", write_file)
    
    # HTTP fetch tool (simulated)
    def fetch_url(url: str) -> str:
        """Fetch URL content (simulated)"""
        return f"Fetching {url} (simulated)"
    
    registry.register("fetch_url", fetch_url)
    
    return registry


def test_type_validators():
    """Test type validation (v0.1.3)"""
    print("\n" + "="*60)
    print("TEST 1: Type Validators")
    print("="*60)
    
    from failcore.core.validate.validators.type import (
        type_check_precondition,
        required_fields_precondition,
        max_length_precondition,
    )
    from failcore.core.validate.validator import ValidatorRegistry
    
    registry = ValidatorRegistry()
    
    # Test 1.1: Type check
    print("\n[1.1] Type check - expect int, got str:")
    validator = type_check_precondition("age", int, required=True)
    result = validator.validate({"params": {"age": "twenty"}})
    print(f"  Valid: {result.valid}")
    print(f"  Message: {result.message}")
    if not result.valid:
        print(f"  Code: {result.code}")
        print(f"  Details: {result.details}")
    
    # Test 1.2: Required fields
    print("\n[1.2] Required fields - missing 'content':")
    validator = required_fields_precondition("path", "content")
    result = validator.validate({"params": {"path": "/tmp/test.txt"}})
    print(f"  Valid: {result.valid}")
    print(f"  Message: {result.message}")
    if not result.valid:
        print(f"  Code: {result.code}")
        print(f"  Details: {result.details}")
    
    # Test 1.3: Max length
    print("\n[1.3] Max length - content too large:")
    validator = max_length_precondition("content", max_length=100)
    result = validator.validate({"params": {"content": "x" * 1000}})
    print(f"  Valid: {result.valid}")
    print(f"  Message: {result.message}")
    if not result.valid:
        print(f"  Code: {result.code}")
        print(f"  Details: {result.details}")
    
    print("\n[OK] Type validators test completed")


def test_network_validators():
    """Test network security validators (SSRF prevention)"""
    print("\n" + "="*60)
    print("TEST 2: Network Validators (SSRF Prevention)")
    print("="*60)
    
    from failcore.core.validate.validators.network import (
        url_safe_precondition,
        internal_ip_block_precondition,
        domain_whitelist_precondition,
        port_range_precondition,
    )
    
    # Test 2.1: Protocol whitelist
    print("\n[2.1] Protocol check - file:// not allowed:")
    validator = url_safe_precondition("url")
    result = validator.validate({"params": {"url": "file:///etc/passwd"}})
    print(f"  Valid: {result.valid}")
    print(f"  Message: {result.message}")
    if not result.valid:
        print(f"  Code: {result.code}")
        print(f"  Details: {result.details}")
    
    # Test 2.2: Internal IP blocking (SSRF)
    print("\n[2.2] SSRF prevention - block localhost:")
    validator = internal_ip_block_precondition("url")
    result = validator.validate({"params": {"url": "http://127.0.0.1:8080/admin"}})
    print(f"  Valid: {result.valid}")
    print(f"  Message: {result.message}")
    if not result.valid:
        print(f"  Code: {result.code}")
        print(f"  Details: {result.details}")
    
    print("\n[2.3] SSRF prevention - block private IP:")
    result = validator.validate({"params": {"url": "http://192.168.1.1/router"}})
    print(f"  Valid: {result.valid}")
    print(f"  Message: {result.message}")
    if not result.valid:
        print(f"  Code: {result.code}")
        print(f"  Details: {result.details}")
    
    # Test 2.4: Domain whitelist
    print("\n[2.4] Domain whitelist - only allow github.com:")
    validator = domain_whitelist_precondition("url", allowed_domains=["api.github.com"])
    result = validator.validate({"params": {"url": "https://evil.com/api"}})
    print(f"  Valid: {result.valid}")
    print(f"  Message: {result.message}")
    if not result.valid:
        print(f"  Code: {result.code}")
        print(f"  Details: {result.details}")
    
    # Test 2.5: Port range
    print("\n[2.5] Port range - only allow 80/443:")
    validator = port_range_precondition("url", allowed_ports={80, 443})
    result = validator.validate({"params": {"url": "http://example.com:8080"}})
    print(f"  Valid: {result.valid}")
    print(f"  Message: {result.message}")
    if not result.valid:
        print(f"  Code: {result.code}")
        print(f"  Details: {result.details}")
    
    print("\n[OK] Network validators test completed")


def test_resource_validators():
    """Test resource quota validators"""
    print("\n" + "="*60)
    print("TEST 3: Resource Validators")
    print("="*60)
    
    from failcore.core.validate.validators.resource import (
        max_file_size_precondition,
        max_payload_size_precondition,
        max_collection_size_precondition,
    )
    
    # Test 3.1: File size limit
    print("\n[3.1] File size limit - check README.md:")
    validator = max_file_size_precondition("path", max_bytes=1024)  # 1KB limit
    result = validator.validate({"params": {"path": "README.md"}})
    print(f"  Valid: {result.valid}")
    print(f"  Message: {result.message}")
    if not result.valid:
        print(f"  Code: {result.code}")
        print(f"  Details: {result.details}")
    
    # Test 3.2: Payload size limit
    print("\n[3.2] Payload size limit - content too large:")
    validator = max_payload_size_precondition("content", max_bytes=100)  # 100 bytes
    result = validator.validate({"params": {"content": "x" * 1000}})
    print(f"  Valid: {result.valid}")
    print(f"  Message: {result.message}")
    if not result.valid:
        print(f"  Code: {result.code}")
        print(f"  Details: {result.details}")
    
    # Test 3.3: Collection size limit
    print("\n[3.3] Collection size limit - too many items:")
    validator = max_collection_size_precondition("items", max_items=10)
    result = validator.validate({"params": {"items": list(range(100))}})
    print(f"  Valid: {result.valid}")
    print(f"  Message: {result.message}")
    if not result.valid:
        print(f"  Code: {result.code}")
        print(f"  Details: {result.details}")
    
    print("\n[OK] Resource validators test completed")


def test_combined_preset():
    """Test combined_safe preset"""
    print("\n" + "="*60)
    print("TEST 4: Combined Safe Preset")
    print("="*60)
    
    # Create session with combined preset
    session = Session(
        trace="examples/test_validators_trace.jsonl",
        validator=presets.combined_safe(
            strict=True,
            allowed_domains=["api.github.com"],
            max_file_mb=1,
            max_payload_mb=0.1
        )
    )
    
    # Register test tools
    def read_file(path: str) -> str:
        """Read file from disk"""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    
    def write_file(path: str, content: str) -> str:
        """Write file to disk"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {len(content)} bytes to {path}"
    
    def fetch_url(url: str) -> str:
        """Fetch URL content (simulated)"""
        return f"Fetching {url} (simulated)"
    
    session.register("read_file", read_file)
    session.register("write_file", write_file)
    session.register("fetch_url", fetch_url)
    
    print("\n[4.1] Test SSRF prevention:")
    result = session.call("fetch_url", url="http://127.0.0.1:8080/admin")
    print(f"  Status: {result.status}")
    if result.error:
        print(f"  Error: {result.error.error_code} - {result.error.message}")
    
    print("\n[4.2] Test domain whitelist:")
    result = session.call("fetch_url", url="https://evil.com/api")
    print(f"  Status: {result.status}")
    if result.error:
        print(f"  Error: {result.error.error_code} - {result.error.message}")
    
    print("\n[4.3] Test path traversal:")
    result = session.call("write_file", path="../etc/passwd", content="hacked")
    print(f"  Status: {result.status}")
    if result.error:
        print(f"  Error: {result.error.error_code} - {result.error.message}")
    
    print("\n[OK] Combined preset test completed")


def main():
    print("="*60)
    print("FailCore v0.1.3 - New Validators Test Suite")
    print("="*60)
    print("\nTesting 3 new validator categories:")
    print("  1. Type validators (type check, required fields, max length)")
    print("  2. Network validators (SSRF prevention, domain whitelist, port range)")
    print("  3. Resource validators (file size, payload size, collection size)")
    
    try:
        # Run tests
        test_type_validators()
        test_network_validators()
        test_resource_validators()
        test_combined_preset()
        
        print("\n" + "="*60)
        print("[OK] All tests completed successfully!")
        print("="*60)
        
    except Exception as e:
        print(f"\n[FAIL] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

