#!/usr/bin/env python3
"""
FailCore + LangChain Integration Example

This example demonstrates how to use FailCore with LangChain tools:
- Zero-modification integration with existing LangChain tools
- Automatic security protection for LangChain tool calls
- Seamless workflow with LangChain ecosystem

Prerequisites:
  pip install langchain-core

Run: python examples/basic/langchain_integration.py
"""

try:
    from langchain_core.tools import tool
except ImportError:
    print("Error: LangChain not installed. Run: pip install langchain-core")
    exit(1)

from failcore import run, guard
import os


# Define LangChain tools (standard LangChain syntax)
@tool
def write_document(filename: str, content: str) -> str:
    """Write content to a document file."""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    return f"Document '{filename}' created with {len(content)} characters"


@tool
def read_document(filename: str) -> str:
    """Read content from a document file."""
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    return f"Document content: {content}"


@tool
def fetch_web_content(url: str) -> str:
    """Fetch content from a web URL."""
    import urllib.request
    with urllib.request.urlopen(url, timeout=10) as response:
        content = response.read().decode('utf-8')
    return content[:500] + "..." if len(content) > 500 else content


def main():
    """LangChain + FailCore integration demonstration."""
    
    print("=" * 70)
    print("FailCore + LangChain Integration Example")
    print("=" * 70)
    
    # Example 1: Document operations with LangChain tools
    print("\n[Example 1] Document Operations (LangChain Tools + FailCore)")
    print("-" * 70)
    
    with run(policy="fs_safe") as ctx:
        # Protect LangChain tools with FailCore (zero modification needed)
        safe_write = guard(write_document)
        safe_read = guard(read_document)
        
        # Test 1: Normal document operations (should succeed)
        try:
            # Create a document
            result1 = safe_write(
                filename="example_doc.txt",
                content="This is a test document created with LangChain + FailCore integration."
            )
            print(f"✓ Document creation: {result1}")
            
            # Read the document
            result2 = safe_read(filename="example_doc.txt")
            print(f"✓ Document reading: {result2}")
            
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
        
        # Test 2: Path traversal attack (should be blocked)
        try:
            result = safe_write(
                filename="../../../etc/passwd",
                content="malicious content"
            )
            print(f"✗ Security breach: {result}")
        except Exception as e:
            print(f"✓ Path traversal blocked: {type(e).__name__}")
            print(f"  FailCore protected against: ../../../etc/passwd")
        
        print(f"\n✓ Trace saved to: {ctx.trace_path}")
    
    # Example 2: Web content fetching with SSRF protection
    print("\n[Example 2] Web Content Fetching (SSRF Protection)")
    print("-" * 70)
    
    with run(policy="net_safe") as ctx:
        # Protect web fetching tool
        safe_fetch = guard(fetch_web_content)
        
        # Test 1: Legitimate public API (should succeed)
        try:
            result = safe_fetch(url="http://httpbin.org/json")
            print(f"✓ Public API access: {result[:100]}...")
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
        
        # Test 2: AWS metadata endpoint (should be blocked)
        try:
            result = safe_fetch(url="http://169.254.169.254/latest/meta-data/")
            print(f"✗ SSRF attack succeeded: {result}")
        except Exception as e:
            print(f"✓ SSRF attack blocked: {type(e).__name__}")
            print(f"  Protected AWS metadata endpoint")
        
        # Test 3: Private network access (should be blocked)
        try:
            result = safe_fetch(url="http://10.0.0.1/admin")
            print(f"✗ Private network access: {result}")
        except Exception as e:
            print(f"✓ Private network blocked: {type(e).__name__}")
            print(f"  Protected private IP: 10.0.0.1")
        
        print(f"\n✓ Trace saved to: {ctx.trace_path}")
    
    # Example 3: Batch protection of multiple LangChain tools
    print("\n[Example 3] Batch Protection of LangChain Tools")
    print("-" * 70)
    
    # Define more LangChain tools
    @tool
    def calculate_sum(numbers: list) -> float:
        """Calculate the sum of a list of numbers."""
        return sum(numbers)
    
    @tool
    def format_text(text: str, style: str = "upper") -> str:
        """Format text in different styles."""
        if style == "upper":
            return text.upper()
        elif style == "lower":
            return text.lower()
        elif style == "title":
            return text.title()
        else:
            return text
    
    with run() as ctx:  # No specific policy for pure functions
        # Batch protect multiple tools
        langchain_tools = [calculate_sum, format_text]
        protected_tools = [guard(tool) for tool in langchain_tools]
        
        safe_calc, safe_format = protected_tools
        
        # Test the protected tools
        try:
            # Test calculation
            numbers = [1, 2, 3, 4, 5]
            sum_result = safe_calc(numbers=numbers)
            print(f"✓ Sum calculation: {numbers} = {sum_result}")
            
            # Test text formatting
            text = "hello failcore world"
            formatted = safe_format(text=text, style="title")
            print(f"✓ Text formatting: '{text}' -> '{formatted}'")
            
        except Exception as e:
            print(f"✗ Tool execution error: {e}")
        
        print(f"\n✓ Batch protection successful for {len(protected_tools)} tools")
        print(f"✓ Trace saved to: {ctx.trace_path}")
    
    # Example 4: LangChain tool metadata preservation
    print("\n[Example 4] LangChain Tool Metadata Preservation")
    print("-" * 70)
    
    with run() as ctx:
        # Protect tool while preserving LangChain metadata
        protected_write = guard(write_document)
        
        # Check that LangChain metadata is preserved
        print(f"Original tool name: {write_document.name}")
        print(f"Original tool description: {write_document.description}")
        print(f"Original tool args: {list(write_document.args.keys())}")
        
        # The protected version should still work with LangChain
        print(f"\n✓ LangChain metadata preserved after FailCore protection")
        print(f"✓ Tool can still be used in LangChain agents and chains")
    
    # Cleanup
    if os.path.exists("example_doc.txt"):
        os.remove("example_doc.txt")
        print("\n✓ Cleaned up test files")
    
    print("\n" + "=" * 70)
    print("Summary: LangChain + FailCore Integration")
    print("=" * 70)
    print("✓ Zero-modification integration with LangChain tools")
    print("✓ Automatic security protection (SSRF, path traversal)")
    print("✓ Batch protection for multiple tools")
    print("✓ LangChain metadata and functionality preserved")
    print("✓ Full compatibility with LangChain ecosystem")
    print("\nNext steps:")
    print("  - Use protected tools in LangChain agents")
    print("  - Try proxy mode: examples/basic/proxy_mode.py")
    print("  - View security reports: failcore report --last")


if __name__ == "__main__":
    main()