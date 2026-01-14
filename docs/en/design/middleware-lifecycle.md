# Middleware Unified Interface

## Optimization 2: Unified Middleware Semantics

FailCore has **two execution systems** with **unified middleware interface**:

### Architecture

```
Local Tools (Executor/Invoker)
  ↓
  Policy/Validator checks
  ↓
  Tool execution
  
Remote Tools (ToolRuntime)
  ↓
  Middleware chain (Policy/Audit/Validation)
  ↓
  Transport (MCP/Proxy)
```

### Unified Middleware Interface

Both systems use the same **three-phase lifecycle**:

```python
class Middleware(ABC):
    async def on_call_start(self, tool, args, ctx, emit) -> Optional[ToolResult]:
        """
        Phase 1: Before execution
        
        Responsibilities:
        - Observe call context
        - Emit progress events
        - MAY short-circuit (return ToolResult for cache/replay/deny)
        
        Returns:
            - None: continue to execution
            - ToolResult: skip execution (cache hit, policy deny, etc.)
        """
        pass
    
    async def on_call_success(self, tool, args, ctx, result, emit) -> None:
        """
        Phase 2: After successful execution
        
        Responsibilities:
        - Audit/log results
        - Validate postconditions
        - Emit metrics
        
        MUST NOT modify result or raise exceptions
        """
        pass
    
    async def on_call_error(self, tool, args, ctx, error, emit) -> None:
        """
        Phase 3: After failed execution
        
        Responsibilities:
        - Log errors
        - Emit metrics
        - Cleanup resources
        
        MUST NOT modify error or suppress exceptions
        """
        pass
```

### Middleware Types

#### Local (Executor/Invoker)
- **Policy**: Check preconditions, sandbox, permissions
- **Validator**: Schema validation, preconditions
- **Auditor**: Record executions to trace

#### Remote (ToolRuntime)
- **PolicyMiddleware**: Same interface, checks remote tool policies
- **ValidationMiddleware**: Same interface, validates remote args
- **AuditMiddleware**: Same interface, records remote calls

### Benefits of Unified Interface

1. **Code Reuse**: Write audit logic once, works for both local/remote
2. **Consistent Semantics**: Same lifecycle, same guarantees
3. **Easy Testing**: Mock middlewares work for both systems
4. **Clear Boundaries**: Each middleware has specific responsibilities

### Key Differences

| Aspect | Local (Executor) | Remote (ToolRuntime) |
|--------|-----------------|---------------------|
| **Data Source** | Local functions | MCP/Proxy servers |
| **Error Phase** | VALIDATE/POLICY/EXECUTE | NETWORK/DECODE/EXECUTE |
| **Short-circuit** | Policy deny | Cache hit, replay |
| **Concurrency** | Thread pool | asyncio tasks |

### Example: Audit Middleware (Works for Both)

```python
class AuditMiddleware(Middleware):
    async def on_call_start(self, tool, args, ctx, emit):
        # Same for local/remote
        emit(ToolEvent(type="audit", message=f"Starting {tool.name}"))
        return None  # Continue execution
    
    async def on_call_success(self, tool, args, ctx, result, emit):
        # Same for local/remote
        self.logger.info(f"Tool {tool.name} succeeded")
    
    async def on_call_error(self, tool, args, ctx, error, emit):
        # Same for local/remote
        self.logger.error(f"Tool {tool.name} failed: {error}")
```

## Guidelines

### DO ✅
- Keep middleware stateless or use thread-safe state
- Emit events via `emit()`, don't print/log directly
- Use `Optional[ToolResult]` return in `on_call_start` for short-circuit
- Preserve error structure (error_code, suggestion, remediation)

### DON'T ❌
- Mutate `CallContext` or `ToolResult` in-place
- Suppress exceptions in `on_call_error`
- Generate `seq` field in events (runtime owns ordering)
- Implement business logic in middleware (keep it cross-cutting)

## Migration Notes

If you have custom middleware:
1. Check it implements the three-phase interface
2. Ensure `on_call_start` returns `Optional[ToolResult]`
3. Don't rely on execution system internals (Executor vs ToolRuntime)
4. Use `ctx.metadata` for cross-cutting concerns

---

**Optimization Complete**: Middleware semantics are now unified across local and remote tool execution.
