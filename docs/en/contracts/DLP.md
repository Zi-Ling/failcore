# Data Loss Prevention (DLP) Module

## Overview

The Data Loss Prevention (DLP) module detects and prevents sensitive data leakage at tool call boundaries. It integrates with taint tracking to detect when sensitive data flows from source tools to sink tools, and applies policy-driven actions (BLOCK, SANITIZE, WARN) based on data sensitivity levels.

## Purpose

DLP answers the question:

> "Is sensitive data being sent to external or high-risk destinations?"

The module is designed to be:
- **Policy-driven**: Configuration from Policy files, not hardcoded
- **Taint-aware**: Uses taint tracking to detect data flow
- **Pattern-based**: Scans parameters for sensitive data patterns
- **Action-oriented**: Supports BLOCK, SANITIZE, WARN, REQUIRE_APPROVAL actions
- **Structured sanitization**: Evidence-safe summaries + path-based redaction

## Core Concepts

### 1. Sensitive Pattern

A **SensitivePattern** defines what constitutes sensitive data:

- **Name**: Pattern name (e.g., "API_KEY_OPENAI")
- **Category**: Pattern category (API_KEY, SECRET_TOKEN, PRIVATE_KEY, PII_EMAIL, PII_PHONE, PII_SSN, PAYMENT_CARD)
- **Pattern**: Compiled regex pattern
- **Severity**: Severity level (1-10)
- **Source**: Pattern source (builtin, community, local)
- **Trust level**: Pattern trust level (trusted, untrusted, unknown)
- **Signature**: SHA256 checksum for verification

### 2. Policy Matrix

The **PolicyMatrix** maps data sensitivity to actions:

- **SECRET**: BLOCK (highest sensitivity)
- **PII**: BLOCK or SANITIZE
- **CONFIDENTIAL**: SANITIZE or WARN
- **INTERNAL**: WARN or ALLOW
- **PUBLIC**: ALLOW (lowest sensitivity)

### 3. DLP Policy

A **DLPPolicy** defines the action to take when sensitive data is detected:

- **Action**: BLOCK, SANITIZE, WARN, REQUIRE_APPROVAL, ALLOW
- **Reason**: Human-readable reason
- **Auto-sanitize**: Enable automatic sanitization
- **Notify**: Send notification on trigger

### 4. Structured Sanitization

The **StructuredSanitizer** provides advanced redaction capabilities:

- **Evidence summaries**: Never contain full sensitive data (hash, last4, token-class only)
- **JSON path-based redaction**: Precise control via JSON key paths
- **Category-specific masking**: Different strategies per data type
- **Usability-preserving**: Optional preservation (domain, last4) for tool functionality

## Architecture

### Components

1. **Pattern Registry** (`rules/dlp.py`):
   - Single source of truth for sensitive patterns
   - Supports source/version/signature/trust_level tracking
   - Enables community patterns adoption

2. **DLPGuardValidator** (`validate/builtin/dlp.py`):
   - Policy-driven validator implementing BaseValidator
   - Integrates with taint tracking via `Context.state["taint_context"]`
   - Scans parameters for sensitive patterns
   - Applies policy matrix actions
   - Uses StructuredSanitizer for sanitization
   - Converts to DecisionV1

3. **StructuredSanitizer** (`guards/dlp/sanitizer.py`):
   - Evidence summaries (hash, last4, token-class)
   - JSON path-based redaction
   - Category-specific masking
   - Usability-preserving options

4. **DLPMiddleware** (`guards/dlp/middleware.py`):
   - Runtime middleware for pre-execution interception
   - Uses TaintContext to detect leakage risks
   - Applies DLP policies (block, sanitize, warn)
   - Records audit events

### Integration Flow

```
TaintContext (mark) → DLPGuardValidator (detect) → PolicyMatrix (action) → StructuredSanitizer (sanitize) → DecisionV1
```

1. TaintMiddleware marks source tools as tainted
2. DLPGuardValidator detects tainted inputs in sink tools
3. PolicyMatrix determines action based on sensitivity
4. StructuredSanitizer sanitizes if action is SANITIZE
5. DecisionV1 emitted with evidence

## Key Features

### 1. Taint-Aware Detection

DLP uses taint tracking to detect data flow:

```python
# In DLPGuardValidator
taint_context = self._get_taint_context(context)
taint_tags = taint_context.detect_tainted_inputs(params, dependencies)
max_sensitivity = self._get_max_sensitivity(taint_tags, pattern_matches)
policy = policy_matrix.get_policy(max_sensitivity)
```

This enables:
- Detection of data flow from source to sink
- Sensitivity-based policy application
- Evidence with taint sources and flow chains

### 2. Pattern-Based Scanning

DLP scans tool parameters for sensitive patterns:

- Uses `DLPPatternRegistry` to get all patterns
- Applies patterns to parameter values
- Records pattern matches in evidence (with summaries, not full data)
- Combines with taint tags to determine max sensitivity

### 3. Structured Sanitization

When policy action is SANITIZE, DLP uses StructuredSanitizer:

**Policy Configuration**:
```yaml
validators:
  dlp_guard:
    config:
      sanitize:
        enabled: true
        mode: partial  # full, partial, summary
        paths: ["user.email", "payment.card"]  # JSON paths to sanitize
        preserve_usability: true
        preserve_domain: true
        preserve_last4: true
```

**Sanitization Modes**:
- **Full**: Complete redaction (irreversible)
- **Partial**: Usability-preserving (keep domain, last4)
- **Summary**: Evidence-only (for audit, not output)

**Category-Specific Masking**:
- **Email**: Preserve domain (`***@example.com`)
- **Payment Card**: Preserve last 4 digits (`****1234`)
- **API Keys**: Preserve prefix and suffix (`sk-****...abcd`)
- **Phone/SSN**: Preserve last 4 digits

### 4. Evidence-Safe Summaries

Evidence never contains full sensitive data:

```json
{
  "pattern_matches": [
    {
      "pattern_name": "API_KEY_OPENAI",
      "pattern_category": "api_key",
      "severity": 10,
      "match_length": 51,
      "match_hash": "a1b2c3d4e5f6g7h8"
    }
  ],
  "sanitization_performed": true,
  "redaction_mode": "partial",
  "paths_sanitized": ["api_key"],
  "preserve_usability": true
}
```

### 5. Policy-Driven Configuration

DLPGuardValidator reads configuration from Policy:

```yaml
validators:
  dlp_guard:
    enabled: true
    enforcement: block
    config:
      strict_mode: true
      min_severity: 5
      scan_params: true
      use_taint_tracking: true
      source_tools: []
      sink_tools:
        - send_email
        - http_post
      sanitize:
        enabled: true
        mode: partial
        paths: []
```

## Configuration

### DLPGuardValidator Config

```yaml
validators:
  dlp_guard:
    enabled: true
    enforcement: block  # block, warn, shadow
    config:
      # Pattern scanning
      strict_mode: true  # Use strict policy matrix
      min_severity: 5  # Minimum pattern severity to report
      scan_params: true  # Scan tool parameters for patterns
      
      # Taint tracking
      use_taint_tracking: true  # Use taint context for detection
      
      # Tool classification
      source_tools: []  # Custom source tools (empty = use TaintContext defaults)
      sink_tools: []  # Custom sink tools (empty = use TaintContext defaults)
      
      # Sanitization
      sanitize:
        enabled: true
        mode: partial  # full, partial, summary
        paths: []  # JSON paths to sanitize (empty = all string values)
        preserve_usability: true
        preserve_domain: true
        preserve_last4: true
```

### Policy Matrix

Default policy matrix (can be overridden):

| Sensitivity | Action | Auto-Sanitize |
|------------|--------|---------------|
| SECRET | BLOCK | false |
| PII | BLOCK | true |
| CONFIDENTIAL | SANITIZE | true |
| INTERNAL | WARN | false |
| PUBLIC | ALLOW | false |

## Evidence Structure

DLP decisions include:

```json
{
  "tool": "send_email",
  "code": "FC_DLP_SECRET_DETECTED",
  "message": "DLP: secret data detected in send_email parameters (sanitized)",
  "risk_level": "critical",
  "evidence": {
    "tool": "send_email",
    "sensitivity": "secret",
    "taint_sources": ["user", "tool"],
    "taint_count": 2,
    "pattern_matches": [
      {
        "pattern_name": "API_KEY_OPENAI",
        "pattern_category": "api_key",
        "severity": 10,
        "match_length": 51,
        "match_hash": "a1b2c3d4e5f6g7h8"
      }
    ],
    "sanitization_performed": true,
    "redaction_mode": "partial",
    "paths_sanitized": ["api_key"],
    "preserve_usability": true,
    "sanitized_params": {
      "to": "user@example.com",
      "body": "API_KEY=sk-****...abcd"
    },
    "scan_cache_hit": false,
    "scan_hash": "a1b2c3d4"
  }
}
```

## Integration with Taint Tracking

DLP depends on taint tracking for:

1. **Source detection**: Identifying which tools produce sensitive data
2. **Flow detection**: Detecting when tainted data flows to sinks
3. **Sensitivity determination**: Using max sensitivity from taint tags
4. **Evidence generation**: Including taint sources and flow chains

**Taint Context Integration**:
```python
# DLPGuardValidator reads from Context.state
taint_context = context.state.get("taint_context")
if taint_context:
    taint_tags = taint_context.detect_tainted_inputs(params, dependencies)
```

## Scan Cache Integration

DLP uses scan cache to avoid duplicate scanning:

- Gate (DLPGuardValidator) scans parameters and stores results
- Enricher (DLPEnricher) reuses cached results
- Evidence includes `scan_cache_hit` and `scan_hash` for audit
- Run-scoped cache prevents cross-run contamination

## Best Practices

1. **Enable taint tracking**: DLP is most effective with taint context
2. **Configure sink tools**: Explicitly list high-risk sinks (send_email, http_post, etc.)
3. **Use structured sanitization**: Enable for usability-preserving redaction
4. **Set min_severity**: Filter out low-severity patterns to reduce noise
5. **Review sanitized params**: Check `sanitized_params` in evidence for audit
6. **Use scan cache**: Improves performance and ensures consistency

## Relationship to Other Systems

- **Taint Tracking**: DLP depends on taint context for flow detection
- **Semantic**: Independent (Semantic detects intent, DLP detects data leakage)
- **Security Validators**: Independent (path traversal, SSRF don't use DLP)
- **Drift**: Independent (post-run analysis, not runtime)

DLP is a **policy enforcement layer** that uses taint tracking and pattern scanning to prevent sensitive data leakage.
