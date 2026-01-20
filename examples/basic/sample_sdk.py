#!/usr/bin/env python3
"""
FailCore Basic Example: SDK Usage Sample

This example demonstrates the most basic usage of FailCore SDK:
- Using @guard() decorator to protect functions
- Basic security policies (fs_safe, net_safe)
- Simple error handling

Run: python examples/basic/sample_sdk.py
"""

from failcore import run, guard
import os


def main():
    """Basic FailCore SDK usage demonstration."""
    
    print("=" * 60)
    print("FailCore Basic Example: SDK Usage Sample")
    print("=" * 60)
    
    # Example 1: File operations with filesystem protection
    print("\n[Example 1] File Operations with Sandbox Protection")
    print("-" * 60)
    
    with run(policy="fs_safe") as ctx:
        
        @guard()
        def write_file(path: str, content: str) -> str:
            """Write content to a file."""
            with open(path, "w") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} bytes to {path}"
        
        @guard()
        def read_file(path: str) -> str:
            """Read content from a file."""
            with open(path, "r") as f:
                return f.read()
        
        # Test 1: Safe file operation (should succeed)
        try:
            result = write_file("test_file.txt", "Hello FailCore!")
            print(f"✓ Safe write: {result}")
            
            content = read_file("test_file.txt")
            print(f"✓ Safe read: Content = '{content}'")
            
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
        
        # Test 2: Dangerous file operation (should be blocked)
        try:
            result = write_file("/etc/passwd", "malicious content")
            print(f"✗ Security breach: {result}")
        except Exception as e:
            print(f"✓ Security protection: {type(e).__name__}")
            print(f"  Blocked dangerous path: /etc/passwd")
        
        print(f"\n✓ Trace saved to: {ctx.trace_path}")
    
    # Example 2: Network operations with SSRF protection
    print("\n[Example 2] Network Operations with SSRF Protection")
    print("-" * 60)
    
    with run(policy="net_safe") as ctx:
        
        @guard()
        def fetch_url(url: str) -> str:
            """Fetch content from a URL."""
            import urllib.request
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.read().decode('utf-8')[:200] + "..."
        
        # Test 1: Safe public URL (should succeed)
        try:
            result = fetch_url("http://httpbin.org/get")
            print(f"✓ Safe request: {result}")
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
        
        # Test 2: SSRF attempt - AWS metadata (should be blocked)
        try:
            result = fetch_url("http://169.254.169.254/latest/meta-data/")
            print(f"✗ Security breach: {result}")
        except Exception as e:
            print(f"✓ SSRF protection: {type(e).__name__}")
            print(f"  Blocked metadata endpoint: 169.254.169.254")
        
        # Test 3: SSRF attempt - private network (should be blocked)
        try:
            result = fetch_url("http://192.168.1.1/admin")
            print(f"✗ Security breach: {result}")
        except Exception as e:
            print(f"✓ Private network protection: {type(e).__name__}")
            print(f"  Blocked private IP: 192.168.1.1")
        
        print(f"\n✓ Trace saved to: {ctx.trace_path}")
    
    # Example 3: Simple calculation (no side effects)
    print("\n[Example 3] Safe Calculations (No Side Effects)")
    print("-" * 60)
    
    with run() as ctx:  # No specific policy needed for pure functions
        
        @guard()
        def calculate(a: float, b: float, operation: str) -> float:
            """Perform basic calculations."""
            if operation == "add":
                return a + b
            elif operation == "multiply":
                return a * b
            elif operation == "divide":
                if b == 0:
                    raise ValueError("Cannot divide by zero")
                return a / b
            else:
                raise ValueError(f"Unknown operation: {operation}")
        
        # Test calculations
        try:
            result1 = calculate(10, 5, "add")
            print(f"✓ Addition: 10 + 5 = {result1}")
            
            result2 = calculate(10, 5, "multiply")
            print(f"✓ Multiplication: 10 * 5 = {result2}")
            
            result3 = calculate(10, 3, "divide")
            print(f"✓ Division: 10 / 3 = {result3:.2f}")
            
        except Exception as e:
            print(f"✗ Calculation error: {e}")
        
        # Test error handling
        try:
            result = calculate(10, 0, "divide")
            print(f"✗ Should have failed: {result}")
        except Exception as e:
            print(f"✓ Error handling: {e}")
        
        print(f"\n✓ Trace saved to: {ctx.trace_path}")
    
    # Cleanup
    if os.path.exists("test_file.txt"):
        os.remove("test_file.txt")
        print("\n✓ Cleaned up test file")
    
    print("\n" + "=" * 60)
    print("Summary: Basic FailCore SDK Usage")
    print("=" * 60)
    print("✓ File operations protected by sandbox")
    print("✓ Network requests protected from SSRF")
    print("✓ Pure functions work without restrictions")
    print("✓ All operations traced for audit")
    print("\nNext steps:")
    print("  - View traces: failcore show")
    print("  - Generate report: failcore report --last")
    print("  - Try LangChain integration: examples/basic/langchain_integration.py")


if __name__ == "__main__":
    main()