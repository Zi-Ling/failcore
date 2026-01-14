# Network Control

This guide explains how to use FailCore to protect network operations and prevent SSRF attacks.

---

## Overview

The network safety policy (`net_safe`) provides:

- ✅ SSRF protection
- ✅ Private network blocking
- ✅ Protocol restrictions
- ✅ Domain allowlist (optional)

---

## Basic Usage

### Enable Network Safety

```python
from failcore import run, guard
import urllib.request

with run(policy="net_safe") as ctx:
    @guard()
    def fetch_url(url: str) -> str:
        """Fetch URL content"""
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.read().decode('utf-8')
    
    # This will succeed (public URL)
    result = fetch_url("https://httpbin.org/get")
    
    # This will be blocked (SSRF)
    try:
        fetch_url("http://169.254.169.254/latest/meta-data/")
    except PolicyDeny:
        print("SSRF blocked")
```

---

## SSRF Protection

### Blocked Addresses

The `net_safe` policy automatically blocks the following addresses:

1. **Local Loopback**
   - `127.0.0.1`
   - `localhost`
   - `::1`

2. **Private Networks**
   - `10.0.0.0/8`
   - `172.16.0.0/12`
   - `192.168.0.0/16`

3. **Link-Local**
   - `169.254.0.0/16`

4. **AWS Metadata Service**
   - `169.254.169.254`

### Examples

```python
with run(policy="net_safe") as ctx:
    @guard()
    def fetch_url(url: str):
        import urllib.request
        with urllib.request.urlopen(url) as response:
            return response.read()
    
    # ❌ Local loopback
    try:
        fetch_url("http://127.0.0.1:8080/api")
    except PolicyDeny as e:
        print(f"Blocked: {e.result.reason}")
        # Output: Blocked: Private network access blocked: '127.0.0.1'
    
    # ❌ Private network
    try:
        fetch_url("http://192.168.1.1/admin")
    except PolicyDeny:
        print("Private network blocked")
    
    # ❌ AWS metadata
    try:
        fetch_url("http://169.254.169.254/latest/meta-data/")
    except PolicyDeny:
        print("AWS metadata service blocked")
    
    # ✅ Public URL
    result = fetch_url("https://api.example.com/data")
```

---

## Protocol Restrictions

### Allowed Protocols

By default, only:
- `http`
- `https`

### Blocked Protocols

The following protocols are blocked:
- `file://`
- `ftp://`
- `gopher://`
- Other non-HTTP protocols

### Examples

```python
with run(policy="net_safe") as ctx:
    @guard()
    def fetch_url(url: str):
        import urllib.request
        with urllib.request.urlopen(url) as response:
            return response.read()
    
    # ✅ HTTP
    fetch_url("http://example.com")
    
    # ✅ HTTPS
    fetch_url("https://example.com")
    
    # ❌ File protocol
    try:
        fetch_url("file:///etc/passwd")
    except PolicyDeny:
        print("File protocol blocked")
```

---

## Port Restrictions

### Allowed Ports

By default, allowed:
- `80` (HTTP)
- `443` (HTTPS)
- `8080` (HTTP alternate)
- `8443` (HTTPS alternate)

### Custom Ports

```python
from failcore.core.validate.templates import net_safe_policy

# Create custom policy
policy = net_safe_policy()
policy.validators["network_ssrf"].config["allowed_ports"] = [80, 443, 3000, 8000]
```

---

## Domain Allowlist

### Enable Allowlist

```python
from failcore.core.validate.templates import net_safe_policy

# Create policy with allowlist
policy = net_safe_policy(allowlist=[
    "https://api.example.com/*",
    "https://*.trusted.com/*",
    "https://service.internal.com/*"
])
```

### Allowlist Format

Supports the following formats:
- Exact match: `https://api.example.com`
- Path wildcard: `https://api.example.com/*`
- Subdomain wildcard: `https://*.example.com/*`

### Examples

```python
# Use allowlist policy
policy = net_safe_policy(allowlist=[
    "https://api.example.com/*",
    "https://*.trusted.com/*"
])

# Only URLs in allowlist are allowed
# All other URLs (including public URLs) are blocked
```

---

## URL Parameter Detection

FailCore automatically detects URLs in the following parameter names:

- `url`
- `uri`
- `endpoint`
- `host`

### Custom URL Parameters

```yaml
validators:
  network_ssrf:
    config:
      url_params: ["custom_url_param", "api_endpoint"]
```

---

## Error Messages

FailCore provides detailed error messages:

```python
try:
    fetch_url("http://169.254.169.254/latest/meta-data/")
except PolicyDeny as e:
    print(e.result.reason)
    # Output: Private network access blocked: '169.254.169.254'
    
    print(e.result.suggestion)
    # Output: Use public internet URLs only. Private IPs and localhost are blocked for security.
    
    print(e.result.error_code)
    # Output: SSRF_BLOCKED
```

---

## Best Practices

### 1. Always Use net_safe Policy

```python
# Good: Enable network safety
with run(policy="net_safe") as ctx:
    pass

# Bad: No network protection
with run(policy="fs_safe") as ctx:
    # Network operations not protected
    pass
```

### 2. Use HTTPS

```python
# Good: HTTPS
fetch_url("https://api.example.com/data")

# Bad: HTTP (use HTTPS if possible)
fetch_url("http://api.example.com/data")
```

### 3. Test SSRF Protection

```python
def test_ssrf_protection():
    with run(policy="net_safe") as ctx:
        @guard()
        def fetch_url(url: str):
            import urllib.request
            with urllib.request.urlopen(url) as response:
                return response.read()
        
        # Should succeed
        fetch_url("https://httpbin.org/get")
        
        # Should be blocked
        try:
            fetch_url("http://169.254.169.254/latest/meta-data/")
            assert False, "Should be blocked"
        except PolicyDeny:
            pass  # Expected behavior
```

### 4. Monitor Network Requests

```python
with run(policy="net_safe") as ctx:
    @guard()
    def fetch_url(url: str):
        import urllib.request
        with urllib.request.urlopen(url) as response:
            return response.read()
    
    fetch_url("https://api.example.com/data")
    
    # View trace file
    print(f"Trace file: {ctx.trace_path}")
    # Run: failcore show {ctx.trace_path}
```

---

## Advanced Configuration

### Disable Internal Network Blocking

```python
from failcore.core.validate.templates import net_safe_policy

# Create policy allowing internal networks (not recommended)
policy = net_safe_policy()
policy.validators["network_ssrf"].config["block_internal"] = False
```

### Custom Protocol List

```python
from failcore.core.validate.templates import net_safe_policy

# Allow FTP (not recommended)
policy = net_safe_policy()
policy.validators["network_ssrf"].config["allowed_schemes"] = ["http", "https", "ftp"]
```

### Forbid User Info

By default, URLs containing credentials (e.g., `http://user:pass@example.com`) are forbidden:

```python
# Default forbidden
policy.validators["network_ssrf"].config["forbid_userinfo"] = True
```

---

## Common Questions

### Q: Why are public URLs also blocked?

A: If domain allowlist is enabled, only URLs in the allowlist are allowed. Disable allowlist or add URLs to allowlist.

### Q: How to allow specific internal services?

A: Not recommended, but if necessary:
1. Disable `block_internal`
2. Or use proxy/gateway to expose internal services as public URLs

### Q: How to protect against DNS rebinding attacks?

A: FailCore's current implementation doesn't resolve DNS. If stronger protection is needed, add DNS resolution and caching at the application layer.

---

## Summary

The network safety policy provides:

- ✅ SSRF protection
- ✅ Private network blocking
- ✅ Protocol restrictions
- ✅ Optional domain allowlist

---

## Next Steps

- [Filesystem Safety](fs-safety.md) - Learn about filesystem protection
- [Cost Control](cost-guard.md) - Learn about cost limits
- [Policy](../concepts/policy.md) - Deep dive into policy system
