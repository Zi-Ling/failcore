# Side-Effect Auditor

## Purpose

The Side-Effect Auditor is a runtime enforcement and audit component that detects
whether an agent’s execution has crossed declared side-effect boundaries.

It exists to answer one core question:

> “Did this agent perform a side-effect operation that it was explicitly not allowed to perform?”

The auditor operates at **execution time**, produces **deterministic findings**,
and can act as a **direct blocking authority**.

---

## What Is a Side-Effect?

A **side-effect** is any operation performed by an agent that may be irreversible
or have persistent impact beyond the model’s internal reasoning.

Side-effects often affect:
- System state
- External resources
- Security boundaries
- Cost or availability

The Side-Effect Auditor does not infer intent.
It records and evaluates **observable execution facts only**.

---

## Scope of Side-Effects

To remain auditable and enforceable, side-effects are classified into a fixed,
closed set of categories.

### 1. Filesystem

Operations that interact with the local filesystem.

Examples:
- Reading files
- Writing or modifying files
- Deleting files or directories

Judged by:
- Tool type (filesystem-related tools)
- Presence of path / file / directory parameters

Typical risk:
- Data loss
- Privilege escalation
- Configuration corruption

Detected via:
- Filesystem boundary checks
- Path drift analysis

---

### 2. Network

Operations that initiate or accept network communication.

Examples:
- Outbound HTTP requests
- Connecting to external hosts
- Accessing private or link-local networks

Judged by:
- Network-related tools
- Presence of host / URL / address parameters

Typical risk:
- Data exfiltration
- SSRF
- Credential leakage

Mitigated via:
- Network boundary enforcement
- Guardian SSRF protection

---

### 3. Exec

Operations that execute external commands or binaries.

Examples:
- Shell commands
- Subprocess execution
- Script invocation

Judged by:
- Exec / shell tool types
- Presence of command or argument parameters

Typical risk:
- Arbitrary code execution
- Environment compromise

---

### 4. Process

Operations that affect process lifecycle or signals.

Examples:
- Spawning new processes
- Killing processes
- Sending signals

Judged by:
- Process control tools
- Signal / PID parameters

Typical risk:
- Service disruption
- Denial of service

---

## Boundary Declaration

A **side-effect boundary** is a declarative specification of which side-effect
categories are allowed during a run.

Boundaries are:
- Run-scoped
- Static for the entire execution
- Deterministic and immutable

Boundaries are provided at run startup and passed to the Side-Effect Auditor.

### Declaration Format

Boundaries are expressed using a minimal, explicit structure.

Example:

```json
{
  "allowed_categories": ["filesystem", "network"],
  "blocked_categories": ["exec", "process"],
  "allowlists": [
    {
      "category": "filesystem",
      "rules": ["path:/tmp/*"]
    }
  ]
}
