# Integrations Overview

FailCore integrates with popular LLM frameworks and protocols to provide execution-time safety.

---

## Supported Integrations

FailCore currently supports:

1. **LangChain** - LangChain tool and agent integration
2. **MCP** - Model Context Protocol support

---

## Integration Philosophy

FailCore's integration approach follows these principles:

### Execution Sovereignty

- FailCore controls **execution**, not planning
- All tool calls flow through FailCore's validation engine
- Frameworks provide tool definitions, FailCore enforces safety

### Zero Breaking Changes

- Integrations are **additive**, not replacements
- Existing code continues to work
- FailCore adds safety without changing behavior

### Transparent Protection

- Tool calls are automatically protected
- No manual policy configuration required per tool
- Policies apply uniformly across all tools

---

## LangChain Integration

FailCore provides seamless integration with LangChain tools and agents.

**Features:**
- Automatic LangChain tool detection
- BaseTool compatibility for agents
- Full async support
- Parameter schema preservation

**See:** [LangChain Integration](langchain.md)

---

## MCP Integration

FailCore supports Model Context Protocol (MCP) for remote tool execution.

**Features:**
- MCP client implementation
- Policy protection for MCP tools
- SSRF and network security
- Cost tracking for remote calls

**See:** [MCP Integration](mcp.md)

---

## Choosing an Integration

### Use LangChain Integration When:

- You're using LangChain agents
- You need BaseTool compatibility
- You want automatic tool detection

### Use MCP Integration When:

- You're using MCP servers
- You need remote tool execution
- You want protocol-level protection

### Use Both When:

- You have a hybrid architecture
- Some tools are local (LangChain), others are remote (MCP)

---

## Next Steps

- [LangChain Integration](langchain.md) - LangChain-specific guide
- [MCP Integration](mcp.md) - MCP-specific guide
- [Deployment Patterns](../getting-started/deployment-patterns.md) - How to deploy
