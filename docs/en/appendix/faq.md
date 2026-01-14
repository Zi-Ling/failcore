# Frequently Asked Questions

This document answers common questions about FailCore.

---

## Installation and Setup

### Q: How do I install FailCore?

A: Install using pip:

```bash
pip install failcore
```

See [Installation Guide](../getting-started/install.md) for details.

### Q: What dependencies are needed?

A: FailCore core runtime has no dependencies. Optional features require additional dependencies:

- `failcore[proxy]`: Proxy mode
- `failcore[langchain]`: LangChain integration
- `failcore[ui]`: Web UI
- `failcore[mcp]`: MCP support

### Q: Which Python versions are supported?

A: Python 3.10 or higher.

---

## Usage

### Q: How do I get started with FailCore?

A: See the [Quick Start](../getting-started/first-run.md) guide.

### Q: What's the difference between @guard() and ctx.tool()?

A: Both methods have the same functionality:

- `@guard()`: Decorator style, more concise
- `ctx.tool()`: Explicit registration, more explicit

Choose the style you prefer.

### Q: How do I customize policies?

A: See the [Policy documentation](../concepts/policy.md).

### Q: Where are trace files saved?

A: By default in `<project root>/.failcore/runs/<date>/<run_id>/trace.jsonl`.

You can customize the path using the `trace` parameter.

---

## Policy and Security

### Q: What's the overhead of policy checks?

A: Typically < 1ms, negligible impact on performance.

### Q: How do I disable policies?

A: Use `policy=None`:

```python
with run(policy=None) as ctx:
    pass
```

**Note:** Not recommended, loses all protection.

### Q: How do I allow specific paths?

A: Use `allow_outside_root` and `allowed_sandbox_roots`:

```python
with run(
    policy="fs_safe",
    sandbox="/tmp/external",
    allow_outside_root=True,
    allowed_sandbox_roots=[Path("/tmp")]
) as ctx:
    pass
```

### Q: How do I test policies?

A: Use policy replay:

```bash
failcore replay report trace.jsonl --policy new_policy.yaml
```

---

## Trace and Replay

### Q: How do I view trace files?

A: Use CLI:

```bash
failcore show
failcore show --run <run_id>
```

### Q: How do I replay execution?

A: Use replay commands:

```bash
failcore replay report trace.jsonl
failcore replay mock trace.jsonl
```

### Q: Can trace files be deleted?

A: Yes, but recommended to keep for auditing and analysis.

---

## Cost Control

### Q: How do I set cost limits?

A: Use `max_cost_usd` parameter:

```python
with run(max_cost_usd=10.0) as ctx:
    pass
```

### Q: Are cost estimates accurate?

A: Cost estimates are approximations based on model pricing. Actual costs may vary due to discounts, bulk pricing, etc.

### Q: How do I view costs?

A: Use report command:

```bash
failcore report --include-cost
```

---

## Troubleshooting

### Q: Tool calls are unexpectedly blocked

A: Check:

1. Policy configuration is correct
2. Paths are within sandbox
3. Use `failcore policy explain` to see why

### Q: Trace files not generated

A: Check:

1. `trace` parameter is correct
2. Write permissions available
3. Use `ctx.trace_path` to view path

### Q: Database not found

A: Import trace files first:

```bash
failcore trace ingest trace.jsonl
```

### Q: Web UI won't start

A: Check:

1. `failcore[ui]` is installed
2. Port is not in use
3. View error messages

---

## Integration

### Q: How do I integrate with LangChain?

A: See LangChain integration documentation (if available) or use `failcore[langchain]`.

### Q: How do I integrate with MCP?

A: See [MCP Protection Guide](../guides/mcp-guard.md).

### Q: Can I use it in Docker?

A: Yes, FailCore is compatible with Docker. See [Why Not Docker](../design/why-not-docker.md) for details.

---

## Performance

### Q: Does FailCore affect performance?

A: Overhead is minimal (< 1ms per check), negligible for most applications.

### Q: How do I optimize performance?

A:

1. Use appropriate policies (don't over-protect)
2. Disable unnecessary features
3. Use asynchronous trace recording

---

## Best Practices

### Q: Which policy should I use?

A:

- File operations: `fs_safe`
- Network operations: `net_safe`
- Comprehensive: `safe`

### Q: How do I test FailCore?

A:

1. Write test cases
2. Use policy replay
3. View trace files

### Q: How do I monitor FailCore?

A:

1. Regularly view trace files
2. Use Web UI
3. Generate reports

---

## Other

### Q: Is FailCore open source?

A: Yes, FailCore is released under the Apache-2.0 license.

### Q: How do I contribute?

A: See the project repository's contribution guidelines.

### Q: How do I report issues?

A: Create an issue in the project repository.

---

## Summary

If you have other questions, please:

1. Check relevant documentation
2. Search issues
3. Create a new issue

---

## Next Steps

- [Glossary](glossary.md) - Learn terminology
- [Roadmap](roadmap.md) - Learn about future plans
- [Quick Start](../getting-started/first-run.md) - Get started
