# failcore/core/validate/rules.py
"""
Validation rule auto-assembly (system-enforced).

This module builds the minimal, non-bypassable validation rules for a tool
based on its ToolMetadata (risk + side effect). It is intentionally small
and framework-agnostic.

User-selectable presets should live elsewhere (e.g., validate/presets.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from ..tools.metadata import SideEffect, ToolMetadata
from .validator import PreconditionValidator, PostconditionValidator
from .validators.security import path_traversal_precondition
from .validators.contract import output_contract_postcondition
from ..contract import ExpectedKind


@dataclass
class ValidationRuleSet:
    """System-enforced validators attached to a tool."""
    preconditions: List[PreconditionValidator] = field(default_factory=list)
    postconditions: List[PostconditionValidator] = field(default_factory=list)

    def extend(self, other: "ValidationRuleSet") -> None:
        self.preconditions.extend(other.preconditions)
        self.postconditions.extend(other.postconditions)

    def is_empty(self) -> bool:
        return not self.preconditions and not self.postconditions


# ---------- helpers ----------

DEFAULT_PATH_PARAM_NAMES: Sequence[str] = (
    "path",
    "file_path",
    "relative_path",
    "filename",
    "output_path",
    "dst",
    "src",
    "source",
    "target",
    "destination",
)

DEFAULT_NETWORK_PARAM_NAMES: Sequence[str] = (
    "url",
    "uri",
    "endpoint",
    "host",
)


def _parse_expected_kind(value: Optional[Any]) -> Optional[ExpectedKind]:
    if value is None:
        return None
    if isinstance(value, ExpectedKind):
        return value
    if isinstance(value, str):
        v = value.strip().upper()
        if v == "JSON":
            return ExpectedKind.JSON
        if v == "TEXT":
            return ExpectedKind.TEXT
    return None


def _maybe_add_network_guard(
    rules: ValidationRuleSet,
    *,
    param_names: Sequence[str],
    allowlist: Optional[Sequence[str]],
) -> None:
    # Import locally to avoid hard dependency / import cycles when network validators are optional.
    from .validators.network import ssrf_precondition  # type: ignore

    rules.preconditions.append(
        ssrf_precondition(*param_names, allowlist=list(allowlist) if allowlist else None)
    )


# ---------- assembler ----------

class RuleAssembler:
    """
    Assemble system-enforced validation rules from ToolMetadata.

    Notes:
    - This does NOT implement policy decisions (allow/warn/block). Policy should be enforced
      by the policy layer. Here we only attach validators that can fail-fast before execution.
    - Exec tools are intentionally not validated here; they should be blocked or gated by policy.
    """

    def __init__(self, sandbox_root: Optional[str] = None):
        self.sandbox_root = sandbox_root

    def assemble(
        self,
        tool_metadata: ToolMetadata,
        *,
        output_contract: Optional[Dict[str, Any]] = None,
        path_param_names: Optional[Sequence[str]] = None,
        network_param_names: Optional[Sequence[str]] = None,
        network_allowlist: Optional[Sequence[str]] = None,
    ) -> ValidationRuleSet:
        """
        Build a ValidationRuleSet for the given tool metadata.

        Args:
            tool_metadata: ToolMetadata (single source of truth)
            output_contract: Optional output contract settings:
                {
                  "expected_kind": "JSON" | "TEXT" | ExpectedKind,
                  "schema": {...}
                }
            path_param_names: Optional override for path-like parameter names
            network_param_names: Optional override for url/endpoint-like parameter names
            network_allowlist: Optional allowlist used by SSRF guard

        Returns:
            ValidationRuleSet
        """
        rules = ValidationRuleSet()

        side_effect = tool_metadata.side_effect
        strict_contract = tool_metadata.requires_strict_mode

        # --- side-effect based preconditions (system baseline) ---
        if side_effect in (SideEffect.WRITE, SideEffect.READ):
            params = tuple(path_param_names or DEFAULT_PATH_PARAM_NAMES)
            rules.preconditions.append(
                path_traversal_precondition(*params, sandbox_root=self.sandbox_root)
            )

        elif side_effect == SideEffect.NETWORK:
            params = tuple(network_param_names or DEFAULT_NETWORK_PARAM_NAMES)
            _maybe_add_network_guard(
                rules,
                param_names=params,
                allowlist=network_allowlist,
            )

        elif side_effect == SideEffect.EXEC:
            # Exec tools should be policy-gated. We do not silently attach weak validators here.
            # If you want an explicit validator, implement it as a policy rule instead.
            pass

        # --- output contract postconditions (optional, but can be system-enforced by presets elsewhere) ---
        if output_contract:
            kind = _parse_expected_kind(output_contract.get("expected_kind"))
            schema = output_contract.get("schema")
            rules.postconditions.append(
                output_contract_postcondition(
                    expected_kind=kind,
                    schema=schema,
                    strict_mode=bool(strict_contract),
                )
            )

        return rules


__all__ = [
    "ValidationRuleSet",
    "RuleAssembler",
]
