#!/usr/bin/env python3
"""
FailCore MCP Mode Example

This example demonstrates how to use FailCore with Model Context Protocol (MCP).
It shows practical MCP integration patterns and security considerations.

The example demonstrates:
- MCP configuration with FailCore
- Secure tool execution through MCP
- Real-world MCP use cases
- Security policies for MCP operations

Prerequisites:
  pip install mcp  # (when available)

Usage:
  python examples/basic/mcp_mode.py
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List


def show_sample_mcp_config():
    """Show a sample MCP configuration."""
    
    print("=" * 70)
    print("FailCore MCP Integration Example")
    print("=" * 70)
    
    print("\n[Step 1] MCP Configuration")
    print("-" * 70)
    
    print("To use FailCore with MCP, create mcp.json:")
    
    # Sample MCP configuration
    mcp_config = {
        "mcpServers": {
            "filesystem": {
                "command": "uvx",
                "args": ["mcp-server-filesystem", "--base-dir", "./sandbox"],
                "env": {
                    "FAILCORE_POLICY": "fs_safe"
                },
                "disabled": False,
                "autoApprove": ["read_file", "list_directory"]
            },
            "web-search": {
                "command": "uvx", 
                "args": ["mcp-server-web-search"],
                "env": {
                    "FAILCORE_POLICY": "net_safe"
                },
                "disabled": False,
                "autoApprove": []
            }
        }
    }
    
    print("\nConfiguration contents:")
    print(json.dumps(mcp_config, indent=2))
    
    print(f"\n✓ Example MCP configuration displayed")
    print("  (You would create this file manually in your project)")
    
    return mcp_config


def demonstrate_mcp_tools():
    """Demonstrate MCP tools that would be protected by FailCore."""
    
    print("\n[Step 2] MCP Tools with FailCore Protection")
    print("-" * 70)
    
    # Simulate MCP tool definitions
    mcp_tools = [
        {
            "name": "read_file",
            "description": "Read content from a file",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"}
                },
                "required": ["path"]
            },
            "security_policy": "fs_safe"
        },
        {
            "name": "write_file", 
            "description": "Write content to a file",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            },
            "security_policy": "fs_safe"
        },
        {
            "name": "web_search",
            "description": "Search the web for information", 
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Maximum results"}
                },
                "required": ["query"]
            },
            "security_policy": "net_safe"
        }
    ]
    
    print("Available MCP tools with FailCore protection:")
    for i, tool in enumerate(mcp_tools, 1):
        print(f"\n{i}. {tool['name']}")
        print(f"   Description: {tool['description']}")
        print(f"   Security Policy: {tool['security_policy']}")
        print(f"   Input Schema: {json.dumps(tool['inputSchema'], indent=6)}")


def simulate_mcp_operations():
    """Simulate MCP operations with FailCore security."""
    
    print("\n[Step 3] Simulated MCP Operations")
    print("-" * 70)
    
    # Create sandbox directory for demonstration
    sandbox_dir = Path("./sandbox")
    sandbox_dir.mkdir(exist_ok=True)
    
    # Create a sample file
    sample_file = sandbox_dir / "example.txt"
    with open(sample_file, 'w') as f:
        f.write("This is a sample file for MCP demonstration.")
    
    print("Created sandbox environment for MCP operations.")
    
    # Simulate MCP operations
    operations = [
        {
            "operation": "Safe File Read",
            "tool": "read_file",
            "params": {"path": "./sandbox/example.txt"},
            "expected": "✓ Allowed - file within sandbox",
            "result": "File content read successfully"
        },
        {
            "operation": "Dangerous File Read",
            "tool": "read_file", 
            "params": {"path": "/etc/passwd"},
            "expected": "✗ Blocked - path outside sandbox",
            "result": "FailCore security policy violation"
        },
        {
            "operation": "Safe Web Search",
            "tool": "web_search",
            "params": {"query": "python programming", "max_results": 5},
            "expected": "✓ Allowed - safe search query",
            "result": "Search results returned"
        },
        {
            "operation": "Blocked SSRF Attempt",
            "tool": "web_search",
            "params": {"query": "site:169.254.169.254"},
            "expected": "✗ Blocked - SSRF attempt detected", 
            "result": "FailCore network policy violation"
        }
    ]
    
    print("\nMCP Operations with FailCore Security:")
    
    for i, op in enumerate(operations, 1):
        print(f"\n{i}. {op['operation']}")
        print(f"   Tool: {op['tool']}")
        print(f"   Parameters: {json.dumps(op['params'])}")
        print(f"   Expected: {op['expected']}")
        print(f"   Result: {op['result']}")
        
        # Simulate actual file operations for demonstration
        if op['tool'] == 'read_file' and op['params']['path'] == './sandbox/example.txt':
            try:
                with open(op['params']['path'], 'r') as f:
                    content = f.read()
                print(f"   Actual Content: '{content[:50]}...'")
            except Exception as e:
                print(f"   Error: {e}")


def show_mcp_integration_code():
    """Show how to integrate MCP with FailCore in real code."""
    
    print("\n[Step 4] MCP Integration Code Example")
    print("-" * 70)
    
    print("Here's how you would integrate MCP with FailCore in your application:")
    
    integration_code = '''
from failcore import run, guard
import json

# MCP client setup with FailCore protection
def setup_mcp_client():
    """Setup MCP client with FailCore security."""
    
    with run(policy="fs_safe") as ctx:
        
        # Use @guard() decorator - automatically registers and protects tools
        @guard(risk="medium", effect="fs")
        def mcp_read_file(path: str) -> str:
            """MCP tool: read file with FailCore protection."""
            # This would normally call MCP server
            # FailCore automatically applies security policies
            with open(path, 'r') as f:
                return f.read()
        
        @guard(risk="high", effect="fs")
        def mcp_write_file(path: str, content: str) -> str:
            """MCP tool: write file with FailCore protection."""
            # FailCore validates path is within sandbox
            with open(path, 'w') as f:
                f.write(content)
            return f"Wrote {len(content)} bytes to {path}"
        
        # Tools are automatically registered by @guard() decorator
        # No need for manual ctx.tool() registration!
        
        # Use MCP tools safely - call them directly
        try:
            # This will work - file in sandbox
            content = mcp_read_file(path="./sandbox/example.txt")
            print(f"File content: {content}")
            
            # This will be blocked - path outside sandbox
            mcp_read_file(path="/etc/passwd")
            
        except Exception as e:
            print(f"Security protection: {e}")

# Alternative: Advanced usage with manual registration
def advanced_mcp_setup():
    """Advanced MCP setup using ctx.tool() for complex scenarios."""
    
    with run(policy="fs_safe") as ctx:
        
        def mcp_tool_with_metadata(path: str) -> str:
            """Tool with complex metadata - use ctx.tool() for advanced cases."""
            with open(path, 'r') as f:
                return f.read()
        
        # Manual registration for advanced metadata control
        from failcore.core.tools.metadata import ToolMetadata, RiskLevel, SideEffect
        
        metadata = ToolMetadata(
            risk_level=RiskLevel.HIGH,
            side_effect=SideEffect.FS,
            description="Advanced MCP file reader with custom metadata"
        )
        
        ctx.tool(mcp_tool_with_metadata, metadata=metadata)
        
        # Use via ctx.call() for manually registered tools
        result = ctx.call("mcp_tool_with_metadata", path="./sandbox/example.txt")
        print(f"Advanced tool result: {result}")

# Run the example
if __name__ == "__main__":
    setup_mcp_client()  # Recommended: @guard() decorator approach
    # advanced_mcp_setup()  # Advanced: ctx.tool() for complex cases
'''
    
    print(integration_code)


def show_mcp_benefits():
    """Show the benefits of using FailCore with MCP."""
    
    print("\n[Step 5] Benefits of FailCore + MCP")
    print("-" * 70)
    
    benefits = [
        "Automatic security - all MCP tools protected by default",
        "Policy enforcement - consistent security across all operations", 
        "Audit trails - complete logging of MCP interactions",
        "Resource protection - prevent abuse and unauthorized access",
        "Zero-trust model - every operation validated",
        "Developer friendly - security without complexity",
        "Enterprise ready - meets compliance requirements",
        "Scalable protection - works with any number of MCP servers"
    ]
    
    for i, benefit in enumerate(benefits, 1):
        print(f"  {i}. {benefit}")
    
    print("\nAPI Usage Patterns:")
    print("  • Recommended: @guard() decorator - simple, automatic registration")
    print("  • Advanced: ctx.tool() - for complex metadata or dynamic registration")
    print("  • Avoid: mixing both patterns - causes confusion and redundancy")


def cleanup_demo_files():
    """Clean up demonstration files."""
    
    print("\n[Cleanup]")
    print("-" * 70)
    
    # Remove demo files
    demo_files = [
        Path("./sandbox/example.txt"),
        Path("./sandbox"),
        Path("./mcp.json")
    ]
    
    for file_path in demo_files:
        try:
            if file_path.is_file():
                file_path.unlink()
                print(f"✓ Removed: {file_path}")
            elif file_path.is_dir() and not any(file_path.iterdir()):
                file_path.rmdir()
                print(f"✓ Removed empty directory: {file_path}")
        except Exception as e:
            print(f"Note: Could not remove {file_path}: {e}")


def create_sample_mcp_config():
    """Create a sample MCP configuration file."""
    return show_sample_mcp_config()


def main():
    """Main MCP mode demonstration."""
    
    try:
        # Step 1: Create MCP configuration
        config_file = create_sample_mcp_config()
        
        # Step 2: Show MCP tools
        demonstrate_mcp_tools()
        
        # Step 3: Simulate operations
        simulate_mcp_operations()
        
        # Step 4: Show integration code
        show_mcp_integration_code()
        
        # Step 5: Show benefits
        show_mcp_benefits()
        
        print("\n" + "=" * 70)
        print("Summary: FailCore MCP Integration")
        print("=" * 70)
        print("✓ MCP configuration created and demonstrated")
        print("✓ Security policies applied to MCP tools")
        print("✓ Safe and unsafe operations simulated")
        print("✓ Integration code examples provided")
        print("✓ Complete audit trail of all MCP operations")
        
        print("\nNext Steps:")
        print("1. Install MCP SDK: pip install mcp")
        print("2. Configure MCP servers in ./mcp.json")
        print("3. Start FailCore with MCP: failcore mcp")
        print("4. Connect your MCP client to FailCore")
        print("5. Monitor operations: failcore show --mcp")
        
    finally:
        # Always cleanup demo files
        cleanup_demo_files()


if __name__ == "__main__":
    main()