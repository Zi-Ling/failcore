# FailCore Examples

This directory contains practical examples demonstrating FailCore's capabilities.

## Basic Examples

### 1. SDK Usage Sample (`basic/sample_sdk.py`)
The most basic FailCore SDK usage with `@guard()` decorator:
- File operations with sandbox protection
- Network requests with SSRF protection  
- Pure function protection
- Basic error handling

```bash
python examples/basic/sample_sdk.py
```

### 2. LangChain Integration (`basic/langchain_integration.py`)
Zero-modification integration with LangChain tools:
- Protect existing LangChain tools automatically
- Batch protection for multiple tools
- Preserve LangChain metadata and functionality
- Full ecosystem compatibility

```bash
pip install langchain-core
python examples/basic/langchain_integration.py
```

### 3. Proxy Mode (`basic/proxy_mode.py`)
Zero-code integration using HTTP proxy:
- Transparent interception of API calls
- No application code changes needed
- Real-time monitoring and security
- Streaming response support

```bash
pip install httpx
python examples/basic/proxy_mode.py
```

### 4. MCP Integration (`basic/mcp_mode.py`)
Model Context Protocol (MCP) integration with FailCore:
- Secure MCP server/client communication
- Tool validation and security enforcement
- Real-time monitoring of MCP interactions
- Policy-based security for all MCP operations

```bash
python examples/basic/mcp_mode.py
```

## Running Examples

All examples are self-contained and include:
- Clear explanations of what they demonstrate
- Expected output descriptions
- Error handling examples
- Cleanup procedures

### Prerequisites

Basic examples only require FailCore:
```bash
pip install failcore
```

Some examples have additional dependencies:
```bash
pip install langchain-core  # for LangChain integration
pip install httpx          # for proxy mode examples
```

### Example Output

Each example generates:
- Console output showing security protections in action
- Trace files for audit and debugging
- Clear success/failure indicators

### Viewing Results

After running examples, you can:
```bash
# View the latest trace
failcore show

# Generate HTML report
failcore report --last > report.html

# List all runs
failcore list
```

## Example Structure

```
examples/
├── basic/                    # Basic usage examples
│   ├── sample_sdk.py        # @guard() decorator basics
│   ├── langchain_integration.py  # LangChain tool protection
│   ├── proxy_mode.py        # HTTP proxy interception
│   └── mcp_mode.py          # MCP integration example
└── README.md               # This file
```

## Next Steps

After trying these examples:

1. **Explore Advanced Features**: Check the documentation for advanced policies, custom rules, and enterprise features

2. **Integration**: Integrate FailCore into your existing AI agent applications

3. **Production Deployment**: Use proxy mode for zero-code production deployment

4. **Monitoring**: Set up continuous monitoring and alerting

## Getting Help

- **Documentation**: https://zi-ling.github.io/failcore/
- **Issues**: https://github.com/zi-ling/failcore/issues
- **Discussions**: https://github.com/zi-ling/failcore/discussions