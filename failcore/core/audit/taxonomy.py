# failcore/core/audit/taxonomy.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


class AgenticRisk(str, Enum):
    """
    OWASP Top 10 for Agentic Applications (2026) risk identifiers.

    NOTE:
    - Keep enum values stable (ASI01..ASI10).
    - Titles are informational; IDs are the canonical contract.
    """

    ASI01_AGENT_GOAL_HIJACK = "ASI01"
    ASI02_TOOL_MISUSE = "ASI02"
    ASI03_IDENTITY_PRIVILEGE_ABUSE = "ASI03"
    ASI04_AGENTIC_SUPPLY_CHAIN_VULNERABILITIES = "ASI04"
    ASI05_UNEXPECTED_CODE_EXECUTION = "ASI05"
    ASI06_MEMORY_CONTEXT_POISONING = "ASI06"
    ASI07_INSECURE_INTER_AGENT_COMMUNICATION = "ASI07"
    ASI08_CASCADING_FAILURES = "ASI08"
    ASI09_HUMAN_AGENT_TRUST_EXPLOITATION = "ASI09"
    ASI10_ROGUE_AGENTS = "ASI10"


@dataclass(frozen=True)
class RiskInfo:
    """
    Human-facing metadata for a risk ID.

    Contract:
    - code must be one of ASI01..ASI10
    - title/summary are presentation strings and may evolve without breaking schema
    """
    code: str
    title: str
    summary: str


# Canonical risk metadata (IDs must match OWASP list; titles are for display).
RISK_INFO: Dict[AgenticRisk, RiskInfo] = {
    AgenticRisk.ASI01_AGENT_GOAL_HIJACK: RiskInfo(
        code="ASI01",
        title="Agent Goal Hijack",
        summary="Hidden prompts or manipulations that alter the agent’s objectives or intent.",
    ),
    AgenticRisk.ASI02_TOOL_MISUSE: RiskInfo(
        code="ASI02",
        title="Tool Misuse",
        summary="Legitimate tools are coerced into harmful actions beyond intended use.",
    ),
    AgenticRisk.ASI03_IDENTITY_PRIVILEGE_ABUSE: RiskInfo(
        code="ASI03",
        title="Identity & Privilege Abuse",
        summary="Credential misuse, impersonation, or privilege escalation enabling overreach.",
    ),
    AgenticRisk.ASI04_AGENTIC_SUPPLY_CHAIN_VULNERABILITIES: RiskInfo(
        code="ASI04",
        title="Agentic Supply Chain Vulnerabilities",
        summary="Poisoned runtime components/tools/registries (e.g., plugin/MCP/A2A ecosystems).",
    ),
    AgenticRisk.ASI05_UNEXPECTED_CODE_EXECUTION: RiskInfo(
        code="ASI05",
        title="Unexpected Code Execution",
        summary="Natural-language execution paths lead to RCE or arbitrary code execution behaviors.",
    ),
    AgenticRisk.ASI06_MEMORY_CONTEXT_POISONING: RiskInfo(
        code="ASI06",
        title="Memory & Context Poisoning",
        summary="Poisoned memory/context reshapes behavior long after the initial interaction.",
    ),
    AgenticRisk.ASI07_INSECURE_INTER_AGENT_COMMUNICATION: RiskInfo(
        code="ASI07",
        title="Insecure Inter-Agent Communication",
        summary="Spoofed or tampered agent-to-agent messages misdirect actions or coordination.",
    ),
    AgenticRisk.ASI08_CASCADING_FAILURES: RiskInfo(
        code="ASI08",
        title="Cascading Failures",
        summary="Failures propagate across steps/tools/pipelines, amplifying impact.",
    ),
    AgenticRisk.ASI09_HUMAN_AGENT_TRUST_EXPLOITATION: RiskInfo(
        code="ASI09",
        title="Human-Agent Trust Exploitation",
        summary="Polished outputs mislead humans into approving risky or harmful actions.",
    ),
    AgenticRisk.ASI10_ROGUE_AGENTS: RiskInfo(
        code="ASI10",
        title="Rogue Agents",
        summary="Misalignment, concealment, or self-directed behavior beyond expected constraints.",
    ),
}


# -----------------------------
# Mapping layer: rule_id -> risks
# -----------------------------
#
# Goal: make taxonomy stable even as policy rules evolve.
# - First try explicit mapping by rule_id (preferred).
# - Then apply heuristic mapping by keywords (best-effort).
#
# IMPORTANT:
# - DO NOT remove risk IDs once published; only add mappings.
# - Keep rule IDs stable (your policy engine should already do this).


# Explicit mapping table (fill with your actual rule IDs).
# Example rule_id format: "P.SSRF.DENY_PRIVATE_NET", "P.FS.DENY_WRITE_OUTSIDE_WORKDIR", etc.
RULE_ID_TO_RISKS: Dict[str, Tuple[AgenticRisk, ...]] = {
    # Network / SSRF / exfil patterns:
    "P.NET.SSRF": (AgenticRisk.ASI02_TOOL_MISUSE,),
    "P.NET.PRIVATE_NET": (AgenticRisk.ASI02_TOOL_MISUSE,),
    "P.NET.EXFIL": (AgenticRisk.ASI02_TOOL_MISUSE, AgenticRisk.ASI08_CASCADING_FAILURES),

    # Filesystem / destructive actions:
    "P.FS.DELETE": (AgenticRisk.ASI02_TOOL_MISUSE,),
    "P.FS.WRITE": (AgenticRisk.ASI02_TOOL_MISUSE,),
    "P.FS.PATH_TRAVERSAL": (AgenticRisk.ASI05_UNEXPECTED_CODE_EXECUTION, AgenticRisk.ASI02_TOOL_MISUSE),

    # Code execution / eval / shell:
    "P.CODE.RCE": (AgenticRisk.ASI05_UNEXPECTED_CODE_EXECUTION,),
    "P.CODE.EVAL": (AgenticRisk.ASI05_UNEXPECTED_CODE_EXECUTION,),

    # Memory / prompt injection style:
    "P.MEM.POISON": (AgenticRisk.ASI06_MEMORY_CONTEXT_POISONING,),
    "P.PROMPT.INJECTION": (AgenticRisk.ASI01_AGENT_GOAL_HIJACK,),

    # Identity / secrets:
    "P.AUTH.PRIV_ESC": (AgenticRisk.ASI03_IDENTITY_PRIVILEGE_ABUSE,),
    "P.SECRETS.LEAK": (AgenticRisk.ASI03_IDENTITY_PRIVILEGE_ABUSE, AgenticRisk.ASI02_TOOL_MISUSE),
}


def risks_for_rule_id(rule_id: Optional[str]) -> List[AgenticRisk]:
    """Return OWASP ASI risks for a given policy rule_id."""
    if not rule_id:
        return []
    if rule_id in RULE_ID_TO_RISKS:
        return list(RULE_ID_TO_RISKS[rule_id])
    return []


# -----------------------------
# Heuristic mapping (best-effort)
# -----------------------------

_KEYWORDS: List[Tuple[Tuple[str, ...], Tuple[AgenticRisk, ...]]] = [
    (("prompt injection", "jailbreak", "goal hijack", "instruction hijack"), (AgenticRisk.ASI01_AGENT_GOAL_HIJACK,)),
    (("tool misuse", "ssrf", "private net", "exfil", "data exfil", "leak"), (AgenticRisk.ASI02_TOOL_MISUSE,)),
    (("credential", "token", "oauth", "privilege", "impersonat", "identity"), (AgenticRisk.ASI03_IDENTITY_PRIVILEGE_ABUSE,)),
    (("mcp", "plugin", "registry", "supply chain", "dependency", "adapter"), (AgenticRisk.ASI04_AGENTIC_SUPPLY_CHAIN_VULNERABILITIES,)),
    (("rce", "exec", "eval", "subprocess", "shell", "code injection"), (AgenticRisk.ASI05_UNEXPECTED_CODE_EXECUTION,)),
    (("memory", "context poisoning", "vector", "retrieval poisoning"), (AgenticRisk.ASI06_MEMORY_CONTEXT_POISONING,)),
    (("a2a", "inter-agent", "message spoof", "agent comm"), (AgenticRisk.ASI07_INSECURE_INTER_AGENT_COMMUNICATION,)),
    (("cascade", "cascading", "chain reaction", "amplif"), (AgenticRisk.ASI08_CASCADING_FAILURES,)),
    (("overtrust", "human trust", "approval", "social engineering"), (AgenticRisk.ASI09_HUMAN_AGENT_TRUST_EXPLOITATION,)),
    (("rogue", "misalignment", "self-directed", "conceal"), (AgenticRisk.ASI10_ROGUE_AGENTS,)),
]


def risks_best_effort(
    *,
    rule_id: Optional[str] = None,
    event_name: Optional[str] = None,
    message: Optional[str] = None,
    tool_name: Optional[str] = None,
) -> List[AgenticRisk]:
    """
    Best-effort risk tagging when explicit rule_id mapping is missing.

    Inputs are intentionally generic so you can feed:
    - policy_denied.event
    - tool_call.name
    - exception messages
    """
    # 1) Prefer explicit mapping by rule_id
    direct = risks_for_rule_id(rule_id)
    if direct:
        return direct

    # 2) Heuristic fallback by keywords
    hay = " ".join([s for s in [rule_id, event_name, message, tool_name] if s]).lower()
    found: List[AgenticRisk] = []
    for keys, risks in _KEYWORDS:
        if any(k in hay for k in keys):
            for r in risks:
                if r not in found:
                    found.append(r)
    return found


def risk_info(risk: AgenticRisk) -> RiskInfo:
    """Get display metadata for a risk."""
    return RISK_INFO[risk]


def risk_codes(risks: Sequence[AgenticRisk]) -> List[str]:
    """Return ASI codes, e.g. ['ASI01', 'ASI02']"""
    return [r.value for r in risks]


def validate_risk_table() -> None:
    """
    Internal sanity check (call from tests):
    - ensure all enums exist in RISK_INFO
    - ensure mapping table only references known enums
    """
    for r in AgenticRisk:
        if r not in RISK_INFO:
            raise ValueError(f"Missing RISK_INFO for {r}")
    for rid, risks in RULE_ID_TO_RISKS.items():
        for r in risks:
            if not isinstance(r, AgenticRisk):
                raise ValueError(f"RULE_ID_TO_RISKS[{rid}] contains non-AgenticRisk: {r!r}")
