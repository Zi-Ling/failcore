# Policy Syntax Reference

Complete reference for FailCore policy file syntax.

---

## Policy File Location

Policy files are stored in:

```
.failcore/validate/<policy-name>.yaml
```

Use custom policies:

```python
run(policy="<policy-name>")
```

---

## Basic Structure

```yaml
# .failcore/validate/my_policy.yaml
validators:
  - name: security_path_traversal
    action: BLOCK
  - name: network_ssrf
    action: WARN
```

---

## Validator Configuration

### Action Types

- `BLOCK`: Block execution if validation fails
- `WARN`: Log warning but allow execution
- `SHADOW`: Record decision but don't block

### Validator Names

Available validators:

#### Security Validators

- `security_path_traversal`: Path traversal protection
- `network_ssrf`: SSRF and private network protection

#### Resource Validators

- `resource_file_size`: File size limits
- `resource_memory`: Memory limits
- `resource_timeout`: Timeout limits

#### Cost Validators

- `cost_budget`: Budget enforcement
- `cost_burn_rate`: Burn rate limits

---

## Validator Examples

### Path Traversal Protection

```yaml
validators:
  - name: security_path_traversal
    action: BLOCK
    config:
      allow_absolute: false
      sandbox_root: "./data"
```

**Configuration:**
- `allow_absolute`: Allow absolute paths (default: `false`)
- `sandbox_root`: Sandbox root directory

### SSRF Protection

```yaml
validators:
  - name: network_ssrf
    action: BLOCK
    config:
      allow_private_ips: false
      allowed_domains:
        - "api.example.com"
        - "*.trusted-domain.com"
```

**Configuration:**
- `allow_private_ips`: Allow private IP ranges (default: `false`)
- `allowed_domains`: Whitelist of allowed domains

### File Size Limits

```yaml
validators:
  - name: resource_file_size
    action: WARN
    config:
      max_size_bytes: 10485760  # 10MB
      check_read: true
      check_write: true
```

**Configuration:**
- `max_size_bytes`: Maximum file size in bytes
- `check_read`: Check read operations (default: `true`)
- `check_write`: Check write operations (default: `true`)

### Budget Enforcement

```yaml
validators:
  - name: cost_budget
    action: BLOCK
    config:
      max_cost_usd: 10.0
      currency: "USD"
```

**Configuration:**
- `max_cost_usd`: Maximum cost in USD
- `currency`: Currency code (default: `"USD"`)

### Burn Rate Limits

```yaml
validators:
  - name: cost_burn_rate
    action: BLOCK
    config:
      max_usd_per_minute: 0.5
      window_minutes: 5
```

**Configuration:**
- `max_usd_per_minute`: Maximum spending rate
- `window_minutes`: Sliding window size (default: `5`)

---

## Complete Policy Example

```yaml
# .failcore/validate/production.yaml
validators:
  # Security
  - name: security_path_traversal
    action: BLOCK
    config:
      allow_absolute: false
      sandbox_root: "./workspace"
  
  - name: network_ssrf
    action: BLOCK
    config:
      allow_private_ips: false
      allowed_domains:
        - "api.production.com"
  
  # Resources
  - name: resource_file_size
    action: WARN
    config:
      max_size_bytes: 52428800  # 50MB
  
  # Cost
  - name: cost_budget
    action: BLOCK
    config:
      max_cost_usd: 100.0
  
  - name: cost_burn_rate
    action: BLOCK
    config:
      max_usd_per_minute: 1.0
      window_minutes: 10
```

---

## Policy Inheritance

Policies can reference other policies:

```yaml
# .failcore/validate/custom.yaml
extends: "safe"  # Inherit from safe preset

validators:
  - name: security_path_traversal
    action: BLOCK
    config:
      sandbox_root: "./custom-sandbox"
```

---

## Conditional Validators

Validators can be conditionally enabled:

```yaml
validators:
  - name: security_path_traversal
    action: BLOCK
    condition:
      effect: "fs"  # Only for filesystem operations
```

---

## Next Steps

- [Configuration Reference](configuration.md) - Complete configuration guide
- [Policy Guide](../concepts/policy.md) - Policy concepts
