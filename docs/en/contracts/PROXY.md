# FailCore Proxy — Execution Chokepoint

> **FailCore Proxy is not a framework, not an SDK, and not an agent system.**
> It is an **execution-time chokepoint** between AI decisions and real-world side effects.

This document defines **what the Proxy is, what it is not, and how it must evolve**.
It serves as a long-term architectural constitution for FailCore.

---

## 1. Why Proxy Exists

Modern AI systems (Agents, Copilots, Automations) do not fail at planning —
they fail at **execution**.

Once an AI system:
- spends money
- sends network requests
- touches files
- executes commands
- outputs sensitive data

**real-world consequences happen.**

FailCore Proxy exists to answer one question:

> **“What happened at execution time, and who is responsible?”**

---

## 2. Core Principle

> **FailCore does not aim to make AI smarter.**
> **FailCore exists to make AI accountable when it touches reality.**

This means:

- Position > Features
- Chokepoint > SDK
- Evidence > Guarantees
- Explainability > Absolute safety

---

## 3. What Is the “Real World”?

In FailCore, *real world* means **irreversible side effects**.

FailCore Proxy only cares about these **execution egresses**:

| Egress | Meaning |
|------|--------|
| NETWORK | HTTP/API requests, data exfiltration |
| FS | File read/write/delete |
| EXEC | shell / subprocess / binaries |
| COST | token usage, API billing |

If an action does **not** belong to one of these, it is **out of scope**.

---

## 4. Architectural Position

FailCore Proxy must sit **between AI and reality**:

```
[ AI / Agent / Script ]
            |
            v
      FailCore Proxy   ← execution chokepoint
            |
            v
[ Network / FS / Exec / Providers ]
```

Anything that bypasses the Proxy is **explicitly unprotected**.

This is intentional.

---

## 5. Non-Goals (Extremely Important)

FailCore Proxy **must never become**:

- an Agent framework
- a planning engine
- a prompt guardrail
- a policy DSL platform
- a compliance certification product
- a “guaranteed safe AI” solution

FailCore **does not promise safety**.
FailCore provides **evidence, control, and accountability**.

---

## 6. Execution Egress Model

Every real-world side effect is normalized into an `EgressEvent`.

Example (conceptual):

```
{
  "egress": "NETWORK",
  "action": "http.request",
  "target": "api.openai.com",
  "summary": "POST /v1/chat/completions",
  "decision": "ALLOW",
  "risk": "high",
  "evidence": {
    "usage": { "total_tokens": 4210 },
    "dlp_hits": ["OPENAI_API_KEY"],
    "taint_source": "user_input"
  }
}
```

**All downstream systems consume `EgressEvent`.**

No module should bypass it.

---

## 7. Proxy Responsibilities

### MUST do
- Transparent request forwarding
- Streaming-safe pass-through (SSE)
- Emit `EgressEvent` for every execution
- Perform fast-path decisions (budget, allowlist)
- Write execution traces
- Support fail-open and degradation

### MUST NOT do
- Heavy computation in request path
- Complex taint propagation
- Deep semantic understanding of agents
- Blocking based on uncertain heuristics
- Stateful user logic

---

## 8. Cost, DLP, and Taint (Correct Positioning)

These features exist **to strengthen evidence**, not to control execution.

### Cost
- Derived from Proxy-visible requests/responses
- Represented as `COST` egress events
- Enables budget and burn-rate protection

### DLP
- Output/request scanning only
- Produces evidence (`dlp_hits`)
- Default behavior: WARN, not BLOCK

### Weak Taint
- Labels source origin (user, model, tool)
- No full variable propagation
- Used for replay and attribution only

---

## 9. Streaming (SSE) Strategy

Default mode:
- Immediate chunk forwarding
- Side-channel scanning (async)
- Evidence-only detection

Optional strict mode:
- Sliding-window scanning
- High-certainty matches only
- Immediate stream termination on violation

Blocking streaming by default is forbidden.

---

## 10. Reliability and Failure Model

FailCore Proxy must be **safe to fail**.

Key rules:
- Fail-open by default
- Bounded queues everywhere
- Drop evidence before dropping traffic
- Never block execution due to tracing
- Proxy failure must not brick AI systems

FailCore is a **control plane**, not a single point of failure.

---

## 11. Trace and Replay

Trace is the **true moat**.

FailCore must ensure:
- Every execution decision is traceable
- Every block/warn is explainable
- Incidents can be reconstructed after the fact

Replay does not need to be perfect —
it needs to be **good enough to answer “what happened”**.

---

## 12. Evolution Strategy

FailCore Proxy evolves vertically, not horizontally.

```
v0.x  Execution interception + trace
v1.x  Reliable replay + incident analysis
v2.x  Cross-agent execution correlation
v3.x  Industry-standard execution evidence
```

Position stays fixed. Capabilities grow around it.

---

## 13. The One-Line Rule

> **FailCore Proxy does not try to stop all failures.**
> **It ensures no failure is silent, untraceable, or unaccountable.**

---

## 14. Final Reminder

If a future feature proposal does not strengthen:
- execution visibility
- accountability
- replay fidelity
- chokepoint positioning

**it does not belong in the Proxy.**
