# CLI Tools

FailCore provides command-line tools for managing traces, generating reports, and analyzing execution.

---

## Command Overview

```bash
failcore <command> [options]
```

Main commands:
- `list` - List recent runs
- `show` - Show run details
- `report` - Generate HTML reports
- `audit` - Audit trace files
- `trace` - Trace file management
- `replay` - Replay execution
- `policy` - Policy management
- `ui` - Launch Web UI

---

## list - List Runs

List recent run records.

### Usage

```bash
failcore list
failcore list --limit 20
```

### Output

```
Run ID                    Date       Status    Steps
abc123...                 2024-01-15 SUCCESS   5
def456...                 2024-01-15 BLOCKED   2
```

### Options

- `--limit <n>`: Show last n records (default: 10)

---

## show - Show Details

Show detailed information about runs or steps.

### Usage

```bash
# Show last run
failcore show

# Show specific run
failcore show --run <run_id>

# Show steps list
failcore show --steps

# Show only errors/blocked steps
failcore show --errors

# Show specific step
failcore show --step <step_id>

# Verbose output
failcore show --verbose
```

### Output Example

```
Run: abc123...
Date: 2024-01-15 10:30:00
Status: SUCCESS
Steps: 5
Duration: 12.5s

Steps:
  1. write_file (SUCCESS) - 2.3ms
  2. read_file (SUCCESS) - 1.1ms
  3. delete_file (BLOCKED) - 0.5ms
```

### Options

- `--run <run_id>`: Show specific run
- `--last`: Show last run (default)
- `--steps`: Show steps list
- `--errors`: Show only errors/blocked steps
- `--step <step_id>`: Show specific step details
- `--verbose, -v`: Verbose output

---

## report - Generate Reports

Generate HTML execution reports.

### Usage

```bash
# Generate report for last run
failcore report

# Generate from trace file
failcore report --trace trace.jsonl
```

### Output

Generates HTML file containing:
- Execution summary
- Timeline
- Step details
- Violation statistics
- Cost analysis

### Options

- `--trace <file>`: Specify trace file path
- `--html`: Generate HTML format (default)

---

## audit - Audit Traces

Analyze trace files to identify violations and anomalies.

### Usage

```bash
# Audit last run
failcore audit

# Audit specific trace file
failcore audit --trace trace.jsonl

# Show recent violations
failcore audit --recent
```

### Output

```
Audit Report
============

Violation Statistics:
  - Policy violations: 2
  - Side-effect boundary crossings: 1
  - Cost overruns: 0

Anomaly Patterns:
  - Path traversal attempts: 1
  - SSRF attempts: 1
```

### Options

- `--trace <file>`: Specify trace file
- `--recent`: Show recent violations

---

## trace - Trace Management

Manage trace files.

### Subcommands

#### ingest - Import Trace

```bash
# Import trace file to database
failcore trace ingest trace.jsonl
```

#### list - List Traces

```bash
# List all trace files
failcore trace list
```

---

## replay - Replay Execution

Replay historical execution.

### Subcommands

#### report - Report Mode

```bash
# Replay with new policy
failcore replay report trace.jsonl --policy new_policy.yaml
```

#### mock - Mock Mode

```bash
# Simulate execution (don't actually run tools)
failcore replay mock trace.jsonl
```

### Options

- `--policy <file>`: Use new policy
- `--mode <mode>`: Replay mode (report/mock)

---

## policy - Policy Management

Manage validation policies.

### Subcommands

#### init - Initialize Policy Directory

```bash
# Create policy files
failcore policy init
```

Creates:
- `active.yaml`: Active policy
- `shadow.yaml`: Shadow policy
- `breakglass.yaml`: Emergency override

#### list-validators - List Validators

```bash
# List all available validators
failcore policy list-validators
```

#### show - Show Policy

```bash
# Show active policy
failcore policy show

# Show shadow policy
failcore policy show --type shadow

# Show merged policy
failcore policy show --type merged
```

#### explain - Explain Policy Decisions

```bash
# Explain why tool was blocked
failcore policy explain --tool write_file --param path=../../etc/passwd
```

### Options

- `--type <type>`: Policy type (active/shadow/breakglass/merged)
- `--format <format>`: Output format (yaml/json)

---

## ui - Web UI

Launch web interface.

### Usage

```bash
# Launch Web UI
failcore ui

# Specify port
failcore ui --port 9000

# Don't auto-open browser
failcore ui --no-browser

# Development mode
failcore ui --dev
```

### Options

- `--host <host>`: Bind host (default: 127.0.0.1)
- `--port <port>`: Bind port (default: 8765)
- `--no-browser`: Don't auto-open browser
- `--dev`: Development mode (auto-reload)

---

## Common Combinations

### View Recent Runs

```bash
# List runs
failcore list

# View details
failcore show --run <run_id>

# Generate report
failcore report --trace <trace_file>
```

### Debug Issues

```bash
# View errors
failcore show --errors

# Audit trace
failcore audit

# Explain policy decisions
failcore policy explain --tool <tool> --param <param>
```

### Test Policies

```bash
# Initialize policy
failcore policy init

# View policy
failcore policy show

# Replay with new policy
failcore replay report trace.jsonl --policy new_policy.yaml
```

---

## Environment Variables

- `FAILCORE_DB_PATH`: Database path
- `FAILCORE_TRACE_DIR`: Trace file directory
- `FAILCORE_POLICY_DIR`: Policy file directory

---

## Common Questions

### Q: Where is the database?

A: Default at `<project root>/.failcore/db.sqlite`. Use `FAILCORE_DB_PATH` environment variable to customize.

### Q: How to import trace files?

A: Use `failcore trace ingest <trace_file>`.

### Q: Where are reports saved?

A: Reports are saved in current directory, filename format: `report_<run_id>.html`.

---

## Summary

CLI tools provide:

- ✅ Run management
- ✅ Trace viewing
- ✅ Report generation
- ✅ Policy management
- ✅ Web UI

---

## Next Steps

- [Web UI](ui.md) - Learn about web interface
- [Reports](reports.md) - Learn about report features
- [Policy Management](../concepts/policy.md) - Deep dive into policies
