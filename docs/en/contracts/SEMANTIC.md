# Semantic Intent Guard Module

## Overview

The Semantic Intent Guard module provides high-confidence detection of malicious patterns in tool calls. It focuses on intent-based and combinatorial risks rather than data leakage, using deterministic parsing and structured rule evaluation for high precision.

## Purpose

Semantic validation answers the question:

> "Does this tool call exhibit malicious intent or dangerous patterns?"

The module is designed to be:
- **High confidence**: 99%+ precision, very low false positive rate
- **Intent-focused**: Detects dangerous combinations, not just individual patterns
- **Deterministic**: Uses structured parsing, not ML or heuristics
- **Explainable**: Clear rule violations with structured evidence
- **Opt-in**: Default disabled, enable only when needed

## Core Concepts

### 1. Semantic Rule

A **SemanticRule** defines a high-confidence malicious pattern:

- **Rule ID**: Unique identifier (e.g., "SEC-001")
- **Category**: Rule category (SECRET_LEAKAGE, PARAM_POLLUTION, DANGEROUS_COMBO, PATH_TRAVERSAL, INJECTION)
- **Severity**: Rule severity (CRITICAL, HIGH, MEDIUM, LOW)
- **Detector**: Detection function (tool_name, params) → bool
- **Source**: Rule source (builtin, community, local)
- **Trust level**: Rule trust level (trusted, untrusted, unknown)
- **Signature**: SHA256 checksum for verification

### 2. Deterministic Parsing

Semantic rules use **deterministic parsers** to convert raw input into structured data:

- **ShellParser**: Tokenizes shell commands (program, flags, args)
- **SQLParser**: Extracts SQL keywords and structure
- **URLParser**: Normalizes URLs and detects internal hosts
- **PathParser**: Normalizes paths and detects traversal
- **PayloadParser**: Parses JSON payloads with JSON paths

This enables rules to evaluate **structured data** instead of raw strings, reducing false positives.

### 3. Rule Categories

Semantic rules are organized by category:

- **SECRET_LEAKAGE**: Detects attempts to leak secrets (e.g., `echo $API_KEY`)
- **PARAM_POLLUTION**: Detects parameter pollution attacks (SQL injection, XSS, etc.)
- **DANGEROUS_COMBO**: Detects dangerous command combinations (e.g., `rm -rf /`)
- **PATH_TRAVERSAL**: Detects path traversal attempts (delegated to security validators in practice)
- **INJECTION**: Detects injection payloads (SQL, command, etc.)

### 4. Responsibility Boundaries

Semantic Intent Guard has clear boundaries:

- **Semantic**: Intent-based/combinatorial risks (dangerous command combos, param pollution, injection payloads)
- **DLP**: Sensitive data leakage (uses Semantic for secret leakage detection, but DLP handles policy)
- **Security Validators**: Path traversal, SSRF (Semantic may detect but doesn't enforce)

## Architecture

### Components

1. **Rule Registry** (`rules/semantic.py`):
   - Single source of truth for semantic rules
   - Supports source/version/signature/trust_level tracking
   - Enables community rules adoption

2. **SemanticDetector** (`guards/semantic/detectors.py`):
   - Evaluates tool calls against semantic rules
   - Filters by severity and category
   - Generates SemanticVerdict with violations

3. **SemanticIntentValidator** (`validate/builtin/semantic.py`):
   - Policy-driven validator wrapping SemanticDetector
   - Converts SemanticVerdict to DecisionV1
   - Integrates deterministic parsers for structured evaluation

4. **Deterministic Parsers** (`guards/semantic/parsers.py`):
   - ShellParser, SQLParser, URLParser, PathParser, PayloadParser
   - Convert raw input to structured AST/features
   - Enable high-confidence rule evaluation

### Integration Flow

```
Raw Input → Parser → Structured Data → Rule Evaluation → SemanticVerdict → DecisionV1
```

## Key Features

### 1. Deterministic Parsing

Semantic rules use parsers to create structured representations:

**Shell Command Parsing**:
```python
parser = ShellParser()
tokens = parser.tokenize("rm -rf /tmp/data")
# Returns: {"program": "rm", "flags": ["-r", "-f"], "args": ["/tmp/data"]}
```

**SQL Parsing**:
```python
parser = SQLParser()
features = parser.extract_keywords("SELECT * FROM users WHERE id=1 UNION SELECT * FROM admin")
# Returns: {"keywords": ["SELECT", "UNION"], "has_comments": false, "stacked_queries": true}
```

**JSON Payload Parsing**:
```python
parser = PayloadParser()
parsed = parser.parse_json('{"user": {"email": "test@example.com"}}')
# Returns: {"valid": true, "paths": ["user.email"], "string_values": ["test@example.com"]}
```

### 2. Structured Rule Evaluation

Rules evaluate structured data, not raw strings:

**Before (Regex-only)**:
```python
if "rm -rf" in command:  # False positive: "echo 'rm -rf is dangerous'"
    return True
```

**After (Structured)**:
```python
tokens = shell_parser.tokenize(command)
if tokens["program"] == "rm" and "-r" in tokens["flags"] and "-f" in tokens["flags"]:
    return True  # High confidence: actual rm -rf command
```

### 3. Policy-Driven Configuration

SemanticIntentValidator reads configuration from Policy:

```yaml
validators:
  semantic_intent:
    enabled: true
    enforcement: block
    config:
      min_severity: high  # Only check HIGH/CRITICAL rules
      enabled_categories:
        - dangerous_combo
        - param_pollution
      block_on_violation: true
```

### 4. Unified Decision Output

SemanticIntentValidator converts SemanticVerdict to DecisionV1:

- One Decision per violated rule
- Evidence includes parsed structure for explainability
- Risk level mapped from rule severity
- Supports active/shadow/breakglass enforcement modes

## Built-in Rules

### SEC-001: Secret Leakage Detection

Detects attempts to leak secrets via echo/print/curl:

- Pattern: Commands that print/output sensitive data
- Severity: CRITICAL
- Example: `echo $API_KEY`, `curl -H "Authorization: Bearer $TOKEN"`

### SEC-002: Parameter Pollution Detection

Detects SQL injection, XSS, command injection:

- Pattern: Injection payloads in parameters
- Severity: HIGH
- Example: SQL injection (`' OR 1=1 --`), XSS (`<script>alert(1)</script>`)

### SEC-003: Path Traversal Detection

Detects path traversal attempts:

- Pattern: `../` sequences or sensitive path access
- Severity: MEDIUM
- Note: Delegated to security validators in practice

### SEC-004: Dangerous Command Detection

Detects dangerous command combinations:

- Pattern: Dangerous flag combinations (e.g., `rm -rf /`, `chmod 777`)
- Severity: CRITICAL
- Example: `rm -rf /`, `chmod -R 777 /`, `dd if=/dev/zero of=/dev/sda`

## Evidence Structure

Semantic decisions include:

```json
{
  "tool": "subprocess.run",
  "code": "FC_SEMANTIC_VIOLATION",
  "message": "Dangerous command detected: rm -rf /",
  "risk_level": "critical",
  "rule_id": "SEC-004",
  "evidence": {
    "tool": "subprocess.run",
    "params": {"command": "rm -rf /"},
    "parsed_structure": {
      "command_shell_ast": {
        "program": "rm",
        "flags": ["-r", "-f"],
        "args": ["/"]
      }
    },
    "violation": {
      "rule_id": "SEC-004",
      "rule_name": "Dangerous Command Detection",
      "severity": "critical",
      "category": "dangerous_combo"
    }
  }
}
```

## Best Practices

1. **Enable selectively**: Semantic guard is opt-in, enable only when needed
2. **Use high severity**: Set `min_severity: high` to reduce false positives
3. **Category filtering**: Enable only relevant categories (e.g., `dangerous_combo` for shell commands)
4. **Review violations**: All violations are explainable, review before blocking
5. **Combine with DLP**: Use Semantic for intent detection, DLP for data leakage

## Relationship to Other Systems

- **DLP**: Independent (DLP handles data leakage, Semantic handles intent)
- **Security Validators**: Overlaps with path traversal, but Semantic focuses on intent, Security focuses on enforcement
- **Taint**: Independent (Semantic doesn't use taint tracking)
- **Drift**: Independent (post-run analysis, not runtime)

Semantic Intent Guard is a **high-confidence signal generator** that complements other validators by detecting malicious intent patterns.
