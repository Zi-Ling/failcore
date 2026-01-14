# Logging & Audit

Guide to logging and audit features in FailCore.

---

## Overview

FailCore provides comprehensive logging and audit capabilities:

- **Structured logging** - JSON-formatted logs
- **Trace files** - Complete execution records
- **Audit logs** - Policy decisions and breakglass activations
- **Cost tracking** - Economic activity logs

---

## Logging

### Log Levels

FailCore uses standard Python logging levels:

- `DEBUG`: Detailed diagnostic information
- `INFO`: General informational messages
- `WARNING`: Warning messages
- `ERROR`: Error messages
- `CRITICAL`: Critical errors

### Configuring Logging

```python
import logging

# Basic configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

# FailCore-specific logger
logger = logging.getLogger('failcore')
logger.setLevel(logging.INFO)
```

### Structured Logging

FailCore logs are structured for easy parsing:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "logger": "failcore.core.executor",
  "message": "Tool execution started",
  "run_id": "run-001",
  "step_id": "step-001",
  "tool": "write_file"
}
```

### Log Output

Logs are written to:

- **Console**: Standard output (default)
- **Files**: Configure file handlers
- **External Systems**: Use logging handlers (e.g., syslog, cloud logging)

```python
import logging
from logging.handlers import RotatingFileHandler

# File handler with rotation
handler = RotatingFileHandler(
    'failcore.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
handler.setFormatter(
    logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
)

logger = logging.getLogger('failcore')
logger.addHandler(handler)
```

---

## Trace Files

### Trace File Format

Trace files are JSONL format (one JSON object per line):

```json
{"event": "STEP_START", "step_id": "abc123", "tool": "write_file", ...}
{"event": "POLICY_CHECK", "step_id": "abc123", "decision": "ALLOW", ...}
{"event": "STEP_END", "step_id": "abc123", "status": "SUCCESS", ...}
```

### Trace File Location

Default location:

```
<project>/.failcore/runs/<date>/<run_id>_<time>/trace.jsonl
```

Custom location:

```python
with run(trace="/var/log/failcore/trace.jsonl") as ctx:
    pass
```

### Trace File Management

#### Rotation

Implement trace file rotation:

```python
import datetime
from pathlib import Path

# Daily rotation
date = datetime.datetime.now().strftime('%Y%m%d')
trace_path = f"traces/trace_{date}.jsonl"

with run(trace=trace_path) as ctx:
    pass
```

#### Compression

Compress old trace files:

```bash
# Compress trace files older than 7 days
find .failcore/runs -name "trace.jsonl" -mtime +7 -exec gzip {} \;
```

#### Cleanup

Remove old trace files:

```bash
# Remove trace files older than 30 days
find .failcore/runs -name "trace.jsonl" -mtime +30 -delete
```

---

## Audit Logging

### Policy Audit

FailCore logs all policy decisions:

```python
from failcore.core.validate.audit import get_audit_logger

audit_logger = get_audit_logger()

# Policy decisions are automatically logged
with run(policy="fs_safe") as ctx:
    pass
```

### Breakglass Audit

Breakglass activations are audited:

```python
from failcore.core.validate.audit import get_audit_logger

audit_logger = get_audit_logger()

# Log breakglass activation
record = audit_logger.log_breakglass_activation(
    policy=policy,
    enabled_by="admin@example.com",
    reason="Emergency maintenance",
    token_used="breakglass-token-123"
)

# Get audit record
audit_record = audit_logger.get_breakglass_audit(policy)
```

### Audit Record Format

```json
{
  "enabled_at": "2024-01-15T10:30:00Z",
  "enabled_by": "admin@example.com",
  "reason": "Emergency maintenance",
  "expires_at": "2024-01-15T11:30:00Z",
  "token_used": "breakglass-token-123",
  "affected_validators": ["security_path_traversal"],
  "affected_decisions": ["BLOCK"]
}
```

---

## Cost Tracking

### Cost Logs

Cost information is logged in trace files:

```json
{
  "event": "COST_TRACKED",
  "step_id": "abc123",
  "cost_usd": 0.001,
  "tokens": 100,
  "model": "gpt-4"
}
```

### Cost Reports

Generate cost reports:

```bash
# Generate cost report
failcore report trace.jsonl --cost

# Output:
# Total Cost: $10.50
# Total Tokens: 105,000
# Average Cost per Request: $0.10
```

---

## Integration with External Systems

### Cloud Logging

Integrate with cloud logging services:

```python
import logging
from google.cloud import logging as cloud_logging

# Google Cloud Logging
client = cloud_logging.Client()
client.setup_logging()

logger = logging.getLogger('failcore')
logger.info("FailCore started")
```

### SIEM Integration

Export logs to SIEM systems:

```python
import logging
from logging.handlers import SysLogHandler

# Syslog handler
handler = SysLogHandler(address=('syslog.example.com', 514))
logger = logging.getLogger('failcore')
logger.addHandler(handler)
```

### Monitoring Systems

Export metrics to monitoring systems:

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram

tool_calls = Counter('failcore_tool_calls_total', 'Total tool calls')
tool_duration = Histogram('failcore_tool_duration_seconds', 'Tool call duration')
```

---

## Best Practices

### Log Retention

- **Development**: 7 days
- **Staging**: 30 days
- **Production**: 90+ days (compliance requirements)

### Log Security

- Encrypt log files at rest
- Use secure log transport (TLS)
- Restrict log file access
- Sanitize sensitive data

### Performance

- Use async logging for high-throughput scenarios
- Implement log buffering
- Use separate storage for logs
- Monitor log file growth

---

## Compliance

### Audit Requirements

FailCore audit logs support compliance requirements:

- **Who**: User/system that made decision
- **What**: Policy decision or breakglass activation
- **When**: Timestamp of action
- **Why**: Reason/justification
- **Where**: Run ID and step ID

### Retention Policies

Implement retention policies:

```python
# Retain audit logs for 7 years (compliance)
import shutil
from datetime import datetime, timedelta

cutoff_date = datetime.now() - timedelta(days=2555)  # 7 years

for audit_file in Path('.failcore/audit').glob('*.jsonl'):
    if datetime.fromtimestamp(audit_file.stat().st_mtime) < cutoff_date:
        # Archive instead of delete
        shutil.move(audit_file, f'archive/{audit_file.name}')
```

---

## Next Steps

- [Deployment](deployment.md) - Production deployment
- [Troubleshooting](troubleshooting.md) - Common logging issues
- [Trace and Replay](../concepts/trace-and-replay.md) - Trace file usage
