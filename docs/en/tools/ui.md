# Web UI

FailCore provides a web interface for viewing traces, runs, and audit reports.

---

## Launch Web UI

### Basic Usage

```bash
failcore ui
```

This will:
1. Start web server (default: http://127.0.0.1:8765)
2. Automatically open browser

### Custom Configuration

```bash
# Specify port
failcore ui --port 9000

# Specify host
failcore ui --host 0.0.0.0

# Don't auto-open browser
failcore ui --no-browser

# Development mode (auto-reload)
failcore ui --dev
```

---

## Features

### 1. Run List

Display all run records:
- Run ID
- Creation time
- Status
- Step count
- Duration

### 2. Run Details

View detailed information for a single run:
- Execution timeline
- All steps
- Policy decisions
- Side-effect records
- Cost analysis

### 3. Step Details

View detailed information for a single step:
- Tool name and parameters
- Policy check results
- Execution results
- Error information (if any)

### 4. Audit Reports

Generate audit reports:
- Violation statistics
- Anomaly patterns
- Timeline analysis
- Cost trends

---

## Interface Overview

### Main Page

```
FailCore Web UI
===============

Recent Runs:
  [Run ID] [Date] [Status] [Steps] [Actions]
  abc123... 2024-01-15 SUCCESS 5 [View] [Report]
  def456... 2024-01-15 BLOCKED 2 [View] [Report]
```

### Run Details Page

```
Run: abc123...
Date: 2024-01-15 10:30:00
Status: SUCCESS
Steps: 5
Duration: 12.5s

Timeline:
  [10:30:00] write_file (SUCCESS)
  [10:30:02] read_file (SUCCESS)
  [10:30:04] delete_file (BLOCKED)
  ...

Step List:
  1. write_file
     Parameters: {path: "test.txt", content: "Hello"}
     Result: SUCCESS
     Duration: 2.3ms
```

### Audit Report Page

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

Timeline:
  [Chart showing execution timeline]
```

---

## Use Cases

### 1. View Run History

```bash
# Launch UI
failcore ui

# In browser:
# 1. View run list
# 2. Click run to view details
# 3. Analyze execution process
```

### 2. Debug Issues

```bash
# Launch UI
failcore ui

# In browser:
# 1. Find failed run
# 2. View step details
# 3. Check policy decisions
# 4. View error information
```

### 3. Generate Reports

```bash
# Launch UI
failcore ui

# In browser:
# 1. Select run
# 2. Click "Generate Report"
# 3. Download HTML report
```

---

## Keyboard Shortcuts

- `j` / `k`: Navigate up/down
- `Enter`: Open details
- `Esc`: Go back
- `/`: Search

---

## Configuration

### Environment Variables

- `FAILCORE_UI_HOST`: Default host
- `FAILCORE_UI_PORT`: Default port
- `FAILCORE_DB_PATH`: Database path

### Configuration Files

Web UI uses the same configuration as CLI:
- Database path: `<project root>/.failcore/db.sqlite`
- Trace directory: `<project root>/.failcore/runs/`

---

## Troubleshooting

### Port Already in Use

```bash
# Use different port
failcore ui --port 9000
```

### Database Not Found

```bash
# Import trace files first
failcore trace ingest trace.jsonl

# Then launch UI
failcore ui
```

### Browser Not Opening

```bash
# Manually open
# http://127.0.0.1:8765
```

---

## Best Practices

### 1. Regular Review

```bash
# Review run history daily
failcore ui
```

### 2. Analyze Trends

```bash
# Use UI to view cost trends
# Identify anomaly patterns
```

### 3. Share Reports

```bash
# Generate reports and share
failcore report --trace trace.jsonl
```

---

## Summary

Web UI provides:

- ✅ Intuitive interface
- ✅ Real-time viewing
- ✅ Interactive analysis
- ✅ Report generation

---

## Next Steps

- [CLI Tools](cli.md) - Learn about command-line tools
- [Reports](reports.md) - Learn about report features
- [Trace and Replay](../concepts/trace-and-replay.md) - Learn about trace system
