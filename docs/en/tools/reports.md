# Reports

FailCore can generate detailed execution reports for analysis and auditing.

---

## Generate Reports

### Basic Usage

```bash
# Generate report for last run
failcore report

# Generate from trace file
failcore report --trace trace.jsonl
```

### Output

Generates HTML file: `report_<run_id>.html`

---

## Report Content

### 1. Execution Summary

- Run ID
- Creation time
- Duration
- Total step count
- Success/failure/blocked statistics

### 2. Timeline

Visual execution timeline:
- Time point for each step
- Step status (success/failure/blocked)
- Duration

### 3. Step Details

Detailed information for each step:
- Tool name
- Parameters
- Policy decisions
- Execution results
- Error information (if any)

### 4. Violation Statistics

- Number of policy violations
- Side-effect boundary crossings
- Cost overruns
- Anomaly patterns

### 5. Cost Analysis

- Total cost
- Cost per step
- Cost trends
- Budget usage

---

## Report Formats

### HTML Reports

Default generates HTML format, containing:
- Interactive timeline
- Collapsible step details
- Charts and visualizations
- Printable version

### JSON Reports

```bash
# Generate JSON format (if supported)
failcore report --format json
```

---

## Use Cases

### 1. Post-Analysis

```bash
# Generate report
failcore report --trace trace.jsonl

# Open in browser
open report_abc123.html
```

### 2. Auditing

```bash
# Generate audit report
failcore audit --trace trace.jsonl

# Generate detailed report
failcore report --trace trace.jsonl
```

### 3. Share Results

```bash
# Generate report
failcore report --trace trace.jsonl

# Share HTML file
# report_abc123.html
```

---

## Report Examples

### Execution Summary

```
Execution Summary
=================

Run ID: abc123...
Created: 2024-01-15 10:30:00
Duration: 12.5s
Total Steps: 5

Statistics:
  - Success: 3
  - Failure: 1
  - Blocked: 1
```

### Timeline

```
Timeline
========

10:30:00.000  write_file (SUCCESS)     2.3ms
10:30:00.002  read_file (SUCCESS)      1.1ms
10:30:00.003  delete_file (BLOCKED)    0.5ms
10:30:00.004  fetch_url (SUCCESS)      8.5ms
10:30:00.012  process_data (FAIL)       0.1ms
```

### Violation Statistics

```
Violation Statistics
====================

Policy Violations: 1
  - delete_file: Path traversal detected

Side-Effect Boundary Crossings: 0

Cost Overruns: 0
```

---

## Custom Reports

### Include Costs

```bash
failcore report --trace trace.jsonl --include-cost
```

### Errors Only

```bash
failcore report --trace trace.jsonl --errors-only
```

---

## Report Best Practices

### 1. Regular Generation

```bash
# Generate reports daily
failcore report
```

### 2. Archive Reports

```bash
# Generate report and archive
failcore report --trace trace.jsonl
mv report_*.html reports/
```

### 3. Analyze Trends

```bash
# Generate multiple reports
for trace in traces/*.jsonl; do
    failcore report --trace "$trace"
done

# Compare reports
```

---

## Report API

### Programmatic Generation

```python
from failcore.cli.views.trace_report import build_report_view_from_trace
from failcore.cli.renderers.html import HtmlRenderer

# Build report view
view = build_report_view_from_trace("trace.jsonl")

# Render to HTML
renderer = HtmlRenderer()
html = renderer.render(view)

# Save
with open("report.html", "w") as f:
    f.write(html)
```

---

## Common Questions

### Q: Where are reports saved?

A: Saved in current directory, filename format: `report_<run_id>.html`.

### Q: How to customize report format?

A: Use report API to programmatically generate custom formats.

### Q: Can reports be exported to other formats?

A: Currently only HTML format is supported. You can use report API to generate other formats.

---

## Summary

Report features provide:

- ✅ Detailed execution analysis
- ✅ Visual timeline
- ✅ Violation statistics
- ✅ Cost analysis

---

## Next Steps

- [CLI Tools](cli.md) - Learn about command-line tools
- [Web UI](ui.md) - Learn about web interface
- [Trace and Replay](../concepts/trace-and-replay.md) - Learn about trace system
