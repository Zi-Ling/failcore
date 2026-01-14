# Deployment

Production deployment guide for FailCore.

---

## Overview

This guide covers production deployment considerations for FailCore, including:

- Infrastructure requirements
- Scaling strategies
- Monitoring and observability
- Security best practices
- Performance optimization

---

## Infrastructure Requirements

### Minimum Requirements

- **CPU**: 2 cores
- **Memory**: 2 GB RAM
- **Storage**: 10 GB (for trace files)
- **Network**: Low latency to LLM providers

### Recommended Requirements

- **CPU**: 4+ cores
- **Memory**: 4+ GB RAM
- **Storage**: 50+ GB (for trace files and audit logs)
- **Network**: Dedicated network path to LLM providers

---

## Deployment Patterns

### Proxy Mode Deployment

Proxy mode is recommended for production:

```bash
# Start proxy server
failcore proxy \
    --listen 0.0.0.0:8000 \
    --upstream https://api.openai.com/v1 \
    --mode strict \
    --budget 100.0
```

#### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install FailCore
RUN pip install "failcore[proxy]"

# Expose proxy port
EXPOSE 8000

# Start proxy
CMD ["failcore", "proxy", "--listen", "0.0.0.0:8000"]
```

#### Systemd Service

```ini
[Unit]
Description=FailCore Proxy
After=network.target

[Service]
Type=simple
User=failcore
WorkingDirectory=/opt/failcore
ExecStart=/usr/local/bin/failcore proxy --listen 0.0.0.0:8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Runtime Mode Deployment

For runtime mode, integrate FailCore into your application:

```python
from failcore import run, guard

# Application code
with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def my_tool():
        pass
```

---

## Scaling Strategies

### Horizontal Scaling

Proxy mode supports horizontal scaling:

1. **Load Balancer**: Place FailCore proxies behind a load balancer
2. **Multiple Instances**: Run multiple proxy instances
3. **Session Affinity**: Use session affinity for stateful operations

```yaml
# Kubernetes example
apiVersion: apps/v1
kind: Deployment
metadata:
  name: failcore-proxy
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: failcore
        image: failcore:latest
        ports:
        - containerPort: 8000
```

### Vertical Scaling

For high-throughput scenarios:

- Increase CPU cores
- Increase memory
- Use faster storage (SSD) for trace files

---

## Monitoring

### Metrics

Monitor key metrics:

- **Request rate**: Requests per second
- **Error rate**: Error percentage
- **Latency**: P50, P95, P99 latencies
- **Cost**: Total cost and burn rate
- **Policy violations**: Security violations per hour

### Logging

FailCore generates structured logs:

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
```

### Trace Files

Monitor trace file growth:

```bash
# Check trace file sizes
du -sh .failcore/runs/*/trace.jsonl

# Rotate old traces
find .failcore/runs -name "trace.jsonl" -mtime +30 -delete
```

---

## Security Best Practices

### Network Security

- Use TLS for proxy connections
- Restrict proxy access to internal networks
- Use firewall rules to limit access

### Authentication

- Use API keys for proxy access
- Implement rate limiting
- Use IP whitelisting

### Policy Configuration

- Use strict policies in production
- Regularly review and update policies
- Enable audit logging

```python
# Production policy
with run(
    policy="fs_safe",
    strict=True,
    sandbox="./workspace"
) as ctx:
    pass
```

---

## Performance Optimization

### Trace File Management

- Use separate storage for trace files
- Compress old trace files
- Implement trace rotation

```python
# Custom trace path with rotation
import datetime

trace_path = f"traces/trace_{datetime.datetime.now().strftime('%Y%m%d')}.jsonl"
with run(trace=trace_path) as ctx:
    pass
```

### Resource Limits

Configure appropriate resource limits:

```python
with run(
    max_cost_usd=100.0,
    max_tokens=100000,
    max_usd_per_minute=1.0
) as ctx:
    pass
```

### Caching

Cache policy configurations:

```python
# Reuse policy objects
from failcore.core.validate.templates import fs_safe_policy

policy = fs_safe_policy(sandbox_root="./data")

# Reuse across runs
with run(policy=policy) as ctx:
    pass
```

---

## High Availability

### Failover

Implement failover strategies:

1. **Multiple Proxies**: Run multiple proxy instances
2. **Health Checks**: Monitor proxy health
3. **Automatic Failover**: Use load balancer for failover

### Backup

Backup critical data:

- Trace files
- Policy configurations
- Audit logs

```bash
# Backup trace files
tar -czf traces_backup_$(date +%Y%m%d).tar.gz .failcore/runs/
```

---

## Disaster Recovery

### Recovery Procedures

1. **Restore from Backups**: Restore trace files and configurations
2. **Replay Traces**: Use trace replay for analysis
3. **Policy Updates**: Update policies based on incidents

### Incident Response

1. **Identify**: Use trace files to identify incidents
2. **Analyze**: Generate reports from traces
3. **Remediate**: Update policies and configurations

---

## Production Checklist

Before deploying to production:

- [ ] Configure appropriate policies
- [ ] Set up monitoring and alerting
- [ ] Configure resource limits
- [ ] Set up backup procedures
- [ ] Test failover scenarios
- [ ] Review security settings
- [ ] Document deployment procedures
- [ ] Train operations team

---

## Next Steps

- [Deployment Patterns](../getting-started/deployment-patterns.md) - Deployment patterns overview
- [Logging & Audit](logging-audit.md) - Logging and audit configuration
- [Troubleshooting](troubleshooting.md) - Common deployment issues
