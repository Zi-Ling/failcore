# FailCore Policy Management Guide

## Overview

FailCore's policy system allows you to manage validation rules through human-readable YAML/JSON files. Policies are stored in `.failcore/validate/` and can be version-controlled, reviewed, and modified without code changes.

## Quick Start

### Initialize Policy Directory

```bash
# Initialize the policy directory with default files
failcore policy init
```

This creates three files in `.failcore/validate/`:
- `active.yaml` - Main policy (enforced)
- `shadow.yaml` - Observation mode (logged only)
- `breakglass.yaml` - Emergency overrides (audited)

### View Current Policy

```bash
# Show active policy
failcore policy show --type active

# Show merged policy (active + shadow + breakglass)
failcore policy show --type merged

# Output as JSON
failcore policy show --type active --format json
```

### Test Policy Impact

```bash
# Explain what validators would trigger for a tool call
failcore policy explain --tool subprocess.run --param command="rm -rf /"
```

## Policy File Structure

### Three-Layer System

FailCore uses a three-layer policy system for safe, progressive enforcement:

1. **active.yaml** - Production rules (enforced)
   - Main policy file
   - Complete and independent
   - Default enforcement: BLOCK
   - Can run standalone

2. **shadow.yaml** - Observation mode (logged, not blocked)
   - Derived from active.yaml
   - All enforcements set to SHADOW
   - Same validators as active
   - Used for testing before enforcement

3. **breakglass.yaml** - Emergency overrides (strictly audited)
   - Temporary exceptions with expiration
   - Global overrides
   - Cannot add new validators
   - All exceptions must have `expires_at`

### Merge Order

When loading policies, FailCore merges in this order:
```
active.yaml → shadow.yaml → breakglass.yaml
```

Each layer can override the previous one, but with restrictions:
- `shadow.yaml` can only change enforcement modes
- `breakglass.yaml` can only add exceptions/overrides, not new validators

## CLI Commands

### `failcore policy init`

Initialize the policy directory with default files.

```bash
failcore policy init
```

**Output:**
```
[OK] Policy directory initialized: .failcore/validate

Created files:
  - active.yaml    (main policy)
  - shadow.yaml    (observation mode)
  - breakglass.yaml (emergency overrides)
```

### `failcore policy list-validators`

List all available validators.

```bash
failcore policy list-validators
```

**Output:**
```
Available Validators:
--------------------------------------------------------------------------------
ID                             Domain          Description
--------------------------------------------------------------------------------
security_path_traversal        security        Path traversal prevention
network_ssrf                    network         SSRF prevention
resource_file_size             resource        File size limits
type_required_fields            type            Type validation
--------------------------------------------------------------------------------
Total: 4 validators
```

### `failcore policy show`

Display policy content.

```bash
# Show active policy
failcore policy show --type active

# Show shadow policy
failcore policy show --type shadow

# Show breakglass policy
failcore policy show --type breakglass

# Show merged policy (all layers combined)
failcore policy show --type merged

# Output as JSON
failcore policy show --type active --format json
```

### `failcore policy generate-shadow`

Generate shadow.yaml from active.yaml with all enforcements set to SHADOW.

```bash
failcore policy generate-shadow
```

**Use Case:** Create a safe testing environment where rules are observed but not enforced.

### `failcore policy validate-file`

Validate a policy file's syntax and structure.

```bash
failcore policy validate-file .failcore/validate/active.yaml
```

**Output:**
```
[OK] Policy file is valid

Policy Summary:
  Version: v1
  Validators: 4
  Description: Default safe policy
```

### `failcore policy explain`

Explain what validators would trigger for a tool call without actually executing it.

```bash
# Test a single tool call
failcore policy explain --tool subprocess.run --param command="rm -rf /"

# Test with multiple parameters
failcore policy explain --tool open --param file="/etc/passwd" --param mode="r"
```

**Output:**
```
Validation Results for: subprocess.run
Parameters: {'command': 'rm -rf /'}

[X] FC_SEC_PATH_TRAVERSAL: Path traversal detected
   Validator: security_path_traversal
   Enforcement: BLOCK
   Allowed: False
   Evidence: {'path': '/', 'reason': 'absolute_path_outside_sandbox'}

Summary:
  Blocked: 1
  Warnings: 0
  Shadowed: 0
```

### `failcore policy diff`

Compare two policy files to see differences.

```bash
failcore policy diff .failcore/validate/active.yaml /tmp/new-policy.yaml
```

**Output:**
```
Comparing:
  .failcore/validate/active.yaml
  /tmp/new-policy.yaml

+ Added validators: expr_rules
~ Modified validators: network_ssrf
[OK] No differences in validators
```

## Web UI

Access the Policy management interface at `/policy` in the FailCore Web UI.

### Available Pages

- **`/policy`** - Overview and quick actions
- **`/policy/validators`** - List all available validators
- **`/policy/editor/{policy_type}`** - Interactive policy editor
  - `active`, `shadow`, `breakglass`, or `merged`
- **`/policy/explain`** - Tool validation simulator
- **`/policy/diff`** - Policy comparison tool

### API Endpoints

All API endpoints are under `/api/policy`:

- `GET /api/policy/validators` - List validators
- `POST /api/policy/init` - Initialize policy directory
- `GET /api/policy/show/{policy_type}` - Get policy content
- `POST /api/policy/save/{policy_type}` - Save policy
- `POST /api/policy/generate-shadow` - Generate shadow policy
- `POST /api/policy/validate-file` - Validate policy syntax
- `POST /api/policy/explain` - Explain validation for tool call
- `POST /api/policy/diff` - Compare two policies

## Policy Configuration

### Validator Configuration

Each validator in a policy has the following structure:

```yaml
validators:
  security_path_traversal:
    id: security_path_traversal
    enabled: true
    enforcement: block  # SHADOW, WARN, or BLOCK
    domain: security
    priority: 30
    config:
      path_params:
        - path
        - file_path
      sandbox_root: null
    exceptions: []
    allow_override: false
```

### Enforcement Modes

- **SHADOW**: Log violations but don't block execution
- **WARN**: Log violations and allow execution (non-blocking)
- **BLOCK**: Block execution if violation detected

### Progressive Enforcement Workflow

1. **Start in SHADOW mode** - Observe violations without blocking
2. **Move to WARN mode** - Alert users but allow execution
3. **Finally BLOCK mode** - Enforce rules strictly

## Data-Driven Rules (expr_rules)

The `expr_rules` validator allows you to define rules in YAML without writing Python code.

### Example Configuration

```yaml
validators:
  expr_rules:
    enabled: true
    enforcement: WARN
    config:
      rules:
        - id: "block_rm_rf"
          tool: "subprocess.run"
          param: "command"
          contains: "rm -rf"
          enforcement: "BLOCK"
          message: "Dangerous rm -rf command detected"
        
        - id: "limit_file_size"
          tool: "open"
          param: "file"
          max_size: 10485760  # 10MB
          enforcement: "WARN"
          message: "File size exceeds 10MB limit"
        
        - id: "block_internal_ips"
          tool: "requests.get"
          param: "url"
          regex: "^(http://)?(10\\.|172\\.(1[6-9]|2[0-9]|3[01])\\.|192\\.168\\.)"
          enforcement: "BLOCK"
          message: "Internal IP address detected"
```

### Supported Conditions

- **`contains`**: Check if string parameter contains a substring
- **`regex`**: Check if parameter matches regex pattern
- **`equals`**: Check if parameter equals specific value
- **`max_size`**: Check if file size exceeds limit (for file paths)

### Tool Name Patterns

Support wildcard patterns:
- `subprocess.*` - Matches all subprocess tools
- `open` - Exact match
- `requests.*` - Matches all requests tools

## Best Practices

### 1. Version Control

Commit policy files to Git:

```bash
git add .failcore/validate/
git commit -m "Update validation policy"
```

### 2. Safe Rollout

```bash
# 1. Generate shadow policy
failcore policy generate-shadow

# 2. Test in shadow mode (observe violations)
# Run your application

# 3. Review violations
# Check logs for shadow mode violations

# 4. Promote to active
cp .failcore/validate/shadow.yaml .failcore/validate/active.yaml
```

### 3. Emergency Overrides

Use `breakglass.yaml` for temporary exceptions:

```yaml
version: v1
validators:
  security_path_traversal:
    exceptions:
      - tool: "backup_script"
        params:
          path: "/backup"
        expires_at: "2024-01-15T00:00:00Z"
        reason: "Emergency backup operation"
```

**Important:** All exceptions must have `expires_at` to prevent permanent bypasses.

### 4. Policy Review

Before deploying policy changes:

```bash
# 1. Validate syntax
failcore policy validate-file .failcore/validate/active.yaml

# 2. Test impact
failcore policy explain --tool your_tool --param key=value

# 3. Compare changes
failcore policy diff .failcore/validate/active.yaml new-policy.yaml

# 4. Review merged policy
failcore policy show --type merged
```

## Usage Examples

### Example 1: Initialize and Configure

```bash
# Initialize policy directory
failcore policy init

# Edit active policy
vim .failcore/validate/active.yaml

# Validate syntax
failcore policy validate-file .failcore/validate/active.yaml

# Test a tool call
failcore policy explain --tool open --param file="/etc/passwd"
```

### Example 2: Safe Rollout

```bash
# Create shadow policy for testing
failcore policy generate-shadow

# Run application with shadow policy
# (violations are logged but not blocked)

# After validation, promote to active
cp .failcore/validate/shadow.yaml .failcore/validate/active.yaml

# Verify changes
failcore policy show --type active
```

### Example 3: Emergency Override

```bash
# Edit breakglass.yaml to add temporary exception
vim .failcore/validate/breakglass.yaml

# Verify merged policy
failcore policy show --type merged

# Exception is now active but will expire automatically
```

### Example 4: Testing New Rules

```bash
# 1. Add new rule to active.yaml
vim .failcore/validate/active.yaml

# 2. Test the rule
failcore policy explain --tool subprocess.run --param command="rm -rf /"

# 3. If satisfied, the rule is already active
# If not, revert the change
```

## Policy Validation Rules

### active.yaml

- Must be a complete PolicyV1 object
- Must contain enabled validators
- Can run standalone
- Default enforcement: BLOCK

### shadow.yaml

- Must have the same validators as active.yaml (set equality)
- Cannot add/remove validators
- Can only change enforcement modes
- Automatically derived from active.yaml

### breakglass.yaml

- Cannot contain validators not in active.yaml
- All exceptions must have `expires_at`
- Cannot modify validator config
- Cannot change validator domain/priority
- Strictly for temporary overrides

## Design Principles

### 1. Policy-First Approach

All tools work directly with policy files, not internal data structures:
- Policies are the single source of truth
- Changes are visible in version control
- Tools are composable (CLI output can be UI input)

### 2. Idempotent Initialization

The `init` command is safe to run multiple times:
- Files are only created if they don't exist
- Existing files are never overwritten
- Safe to include in startup scripts

### 3. Explain Before Enforce

Always test policy impact before deployment:
```bash
failcore policy explain --tool your_tool --param key=value
```

### 4. Diff for Review

Review policy changes like code:
```bash
failcore policy diff old-policy.yaml new-policy.yaml
```

## Troubleshooting

### Policy Not Loading

```bash
# Check if policy directory exists
ls -la .failcore/validate/

# Reinitialize if needed
failcore policy init

# Validate syntax
failcore policy validate-file .failcore/validate/active.yaml
```

### Validator Not Triggering

```bash
# Check if validator is enabled
failcore policy show --type active | grep your_validator

# Test with explain command
failcore policy explain --tool your_tool --param key=value

# Check validator registration
failcore policy list-validators
```

### Breakglass Not Working

- Ensure `expires_at` is set and in the future
- Check that exception matches tool and params exactly
- Verify breakglass.yaml is valid: `failcore policy validate-file .failcore/validate/breakglass.yaml`

## Next Steps

- **Community Rules Repository**: Share rule sets as YAML files
- **Policy Templates**: Pre-configured policies (strict, permissive, development)
- **Policy Versioning**: Track policy changes over time
- **Audit Log**: Track who changed what policy when
- **Monaco Editor**: Enhanced YAML editing in Web UI

## See Also

- [Validation Architecture](../contracts/VALIDATION.md) - Technical architecture details
- [API Reference](../../README.md) - Complete API documentation
