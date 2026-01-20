#!/usr/bin/env python3
"""
FailCore Proxy Mode Example

This example shows how to use FailCore's proxy mode to add security
to existing applications without any code changes.

The example demonstrates:
- How to configure applications to use FailCore proxy
- Making API calls through the proxy
- Seeing security policies in action
- Viewing audit trails

Prerequisites:
  pip install requests  # for making HTTP requests

Usage:
  python examples/basic/proxy_mode.py
"""

import os
import sys
import time
import json
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip install requests")
    exit(1)


def demonstrate_proxy_usage():
    """Demonstrate how to use FailCore proxy with a real application."""
    
    print("=" * 70)
    print("FailCore Proxy Mode Example")
    print("=" * 70)
    
    print("\nThis example shows how to add FailCore security to existing")
    print("applications using proxy mode - no code changes required!")
    
    # Show how to configure proxy
    print("\n[Step 1] Configure Your Application")
    print("-" * 70)
    
    print("Set environment variables to route traffic through FailCore:")
    print("  export HTTP_PROXY=http://127.0.0.1:8080")
    print("  export HTTPS_PROXY=http://127.0.0.1:8080")
    print("\nOr configure in your application:")
    
    # Example 1: Using requests library
    print("\n1. Using Python requests:")
    print("   import requests")
    print("   proxies = {")
    print("       'http': 'http://127.0.0.1:8080',")
    print("       'https': 'http://127.0.0.1:8080'")
    print("   }")
    print("   response = requests.get('https://api.example.com', proxies=proxies)")
    
    # Example 2: Using environment variables
    print("\n2. Using environment variables (works with any HTTP client):")
    
    # Simulate setting proxy environment variables
    proxy_url = "http://127.0.0.1:8080"
    
    # Show current proxy configuration
    current_http_proxy = os.environ.get('HTTP_PROXY', 'Not set')
    current_https_proxy = os.environ.get('HTTPS_PROXY', 'Not set')
    
    print(f"   Current HTTP_PROXY: {current_http_proxy}")
    print(f"   Current HTTPS_PROXY: {current_https_proxy}")
    
    # Example 3: Making actual requests (simulated)
    print("\n[Step 2] Make API Calls (Simulated)")
    print("-" * 70)
    
    print("Your application makes normal API calls:")
    print("The FailCore proxy automatically intercepts and protects them.")
    
    # Simulate some API calls that would go through proxy
    api_calls = [
        {
            "name": "Safe API Call",
            "url": "https://httpbin.org/get",
            "description": "Normal API call - allowed through proxy",
            "expected": "✓ Success - request completed safely"
        },
        {
            "name": "Blocked SSRF Attempt", 
            "url": "http://169.254.169.254/latest/meta-data/",
            "description": "AWS metadata access - blocked by proxy",
            "expected": "✗ Blocked - SSRF attack prevented"
        },
        {
            "name": "Private Network Access",
            "url": "http://192.168.1.1/admin",
            "description": "Private network access - blocked by proxy", 
            "expected": "✗ Blocked - private network protection"
        }
    ]
    
    for i, call in enumerate(api_calls, 1):
        print(f"\n{i}. {call['name']}:")
        print(f"   URL: {call['url']}")
        print(f"   Description: {call['description']}")
        print(f"   Expected Result: {call['expected']}")
    
    # Show what happens without actually making calls
    print("\n[Step 3] Security in Action")
    print("-" * 70)
    
    print("When you run your application with FailCore proxy:")
    print("  ✓ All HTTP/HTTPS requests are intercepted")
    print("  ✓ Security policies are applied automatically")
    print("  ✓ Dangerous requests are blocked")
    print("  ✓ All activity is logged for audit")
    print("  ✓ Your application code remains unchanged")


def show_proxy_setup():
    """Show how to set up the FailCore proxy server."""
    
    print("\n[Proxy Server Setup]")
    print("-" * 70)
    
    print("1. Start FailCore proxy server:")
    print("   failcore proxy --port 8080 --host 127.0.0.1")
    print("\n2. Configure security policy (optional):")
    print("   failcore proxy --port 8080 --policy net_safe")
    print("\n3. Enable audit logging:")
    print("   failcore proxy --port 8080 --trace auto")
    print("\n4. Set resource limits:")
    print("   failcore proxy --port 8080 --max-requests 1000")


def show_real_world_example():
    """Show a real-world example of using proxy mode."""
    
    print("\n[Real-World Example: Existing OpenAI Application]")
    print("-" * 70)
    
    print("Suppose you have an existing application using OpenAI:")
    
    # Show original code
    print("\nOriginal application code:")
    print("```python")
    print("import openai")
    print("client = openai.OpenAI(api_key='your-key')")
    print("response = client.chat.completions.create(")
    print("    model='gpt-3.5-turbo',")
    print("    messages=[{'role': 'user', 'content': 'Hello'}]")
    print(")")
    print("```")
    
    print("\nTo add FailCore security (NO CODE CHANGES):")
    print("1. Start FailCore proxy: failcore proxy --port 8080")
    print("2. Set environment variable: export HTTPS_PROXY=http://127.0.0.1:8080")
    print("3. Run your application normally")
    
    print("\nFailCore automatically provides:")
    print("  ✓ Cost tracking and budget limits")
    print("  ✓ Rate limiting and abuse prevention")
    print("  ✓ Complete audit trail of all API calls")
    print("  ✓ Security policy enforcement")
    print("  ✓ Real-time monitoring and alerts")


def show_monitoring_and_audit():
    """Show how to monitor and audit proxy activity."""
    
    print("\n[Monitoring and Audit]")
    print("-" * 70)
    
    print("After running your application through FailCore proxy:")
    
    print("\n1. View real-time activity:")
    print("   failcore show --live")
    
    print("\n2. Generate audit reports:")
    print("   failcore report --proxy --last-24h")
    
    print("\n3. Check security violations:")
    print("   failcore audit --violations --since yesterday")
    
    print("\n4. Monitor costs and usage:")
    print("   failcore cost --summary --by-application")
    
    print("\n5. Export audit logs:")
    print("   failcore export --format json --output audit.json")


def main():
    """Main proxy mode demonstration."""
    
    # Show basic proxy usage
    demonstrate_proxy_usage()
    
    # Show setup instructions
    show_proxy_setup()
    
    # Show real-world example
    show_real_world_example()
    
    # Show monitoring capabilities
    show_monitoring_and_audit()
    
    print("\n" + "=" * 70)
    print("Summary: FailCore Proxy Mode Benefits")
    print("=" * 70)
    print("✓ Zero code changes - works with existing applications")
    print("✓ Universal compatibility - works with any HTTP client")
    print("✓ Comprehensive security - SSRF, rate limiting, validation")
    print("✓ Complete audit trail - every request logged and traceable")
    print("✓ Real-time monitoring - live visibility into API usage")
    print("✓ Cost control - budget limits and usage tracking")
    print("✓ Easy deployment - single proxy server protects all apps")
    
    print("\nNext Steps:")
    print("1. Start proxy server: failcore proxy --port 8080")
    print("2. Configure your application to use the proxy")
    print("3. Run your application normally")
    print("4. Monitor activity: failcore show")
    print("5. Generate reports: failcore report --proxy")


if __name__ == "__main__":
    main()