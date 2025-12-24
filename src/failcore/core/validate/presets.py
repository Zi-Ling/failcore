# failcore/core/validate/presets.py
"""
Validation presets for common safety patterns.

This module provides opinionated, reusable presets that compose validators
from failcore.core.validate.validators.* into a single bundle.

A preset is framework-agnostic: it only returns lists of preconditions and
postconditions that can be attached to tools or sessions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .validator import PreconditionValidator, PostconditionValidator

from .validators.security import path_traversal_precondition
from .validators.network import ssrf_precondition

# Optional validators (if present in your repo)
# If a function name differs in your implementation, just rename imports here.
try:
    from .validators.resource import (
        max_file_size_precondition,
        max_payload_size_precondition,
        max_collection_size_precondition,
    )
except Exception:  # pragma: no cover
    max_file_size_precondition = None
    max_payload_size_precondition = None
    max_collection_size_precondition = None

try:
    from .validators.type import (
        type_check_precondition,
        required_fields_precondition,
        max_length_precondition,
    )
except Exception:  # pragma: no cover
    type_check_precondition = None
    required_fields_precondition = None
    max_length_precondition = None

try:
    from .validators.contract import output_contract_postcondition
    from ..contract import ExpectedKind
except Exception:  # pragma: no cover
    output_contract_postcondition = None
    ExpectedKind = None


_DEFAULT_PATH_PARAM_NAMES: Tuple[str, ...] = ("path", "file_path", "relative_path", "filename", "output_path", "dst")
_DEFAULT_URL_PARAM_NAMES: Tuple[str, ...] = ("url", "uri", "endpoint", "host")


@dataclass
class ValidationPreset:
    """
    A reusable bundle of validators.
    """
    name: str
    description: str = ""
    preconditions: List[PreconditionValidator] = field(default_factory=list)
    postconditions: List[PostconditionValidator] = field(default_factory=list)

    def add_pre(self, v: PreconditionValidator) -> "ValidationPreset":
        self.preconditions.append(v)
        return self

    def add_post(self, v: PostconditionValidator) -> "ValidationPreset":
        self.postconditions.append(v)
        return self
    
    def to_rule_set(self) -> "ValidationRuleSet":
        """Convert preset to ValidationRuleSet"""
        from .rules import ValidationRuleSet
        rules = ValidationRuleSet()
        rules.preconditions.extend(self.preconditions)
        rules.postconditions.extend(self.postconditions)
        return rules


def fs_safe_sandbox(
    sandbox_root: Optional[str] = None,
    path_params: Sequence[str] = _DEFAULT_PATH_PARAM_NAMES,
) -> ValidationPreset:
    """
    Filesystem sandbox preset:
    - Blocks path traversal
    - Enforces sandbox boundary (via resolve + relative_to)
    """
    preset = ValidationPreset(
        name="fs_safe_sandbox",
        description="Filesystem sandbox with path traversal protection",
    )
    preset.add_pre(
        path_traversal_precondition(*list(path_params), sandbox_root=sandbox_root)
    )
    return preset


def net_safe(
    allowlist: Optional[Sequence[str]] = None,
    url_params: Sequence[str] = _DEFAULT_URL_PARAM_NAMES,
    block_internal: bool = True,
    allowed_schemes: Optional[Set[str]] = None,
    allowed_ports: Optional[Set[int]] = None,
    forbid_userinfo: bool = True,
) -> ValidationPreset:
    """
    Network safety preset:
    - Scheme allowlist (default http/https)
    - Optional domain allowlist
    - Blocks internal networks (literal IPs + localhost)
    - Port allowlist (default 80/443)
    """
    preset = ValidationPreset(
        name="net_safe",
        description="Network SSRF protection with scheme/domain/port controls",
    )
    preset.add_pre(
        ssrf_precondition(
            *list(url_params),
            allowlist=list(allowlist) if allowlist else None,
            block_internal=block_internal,
            allowed_schemes=allowed_schemes,
            allowed_ports=allowed_ports,
            forbid_userinfo=forbid_userinfo,
        )
    )
    return preset


def resource_limits(
    max_file_mb: Optional[float] = None,
    max_payload_mb: Optional[float] = None,
    max_items: Optional[int] = None,
    file_param_names: Sequence[str] = ("path", "file_path", "relative_path", "filename"),
    payload_param_names: Sequence[str] = ("content", "body", "payload"),
    collection_param_names: Sequence[str] = ("items", "rows", "records"),
) -> ValidationPreset:
    """
    Resource limiting preset (optional):
    - File size limit
    - Payload size limit
    - Collection size limit
    """
    preset = ValidationPreset(
        name="resource_limits",
        description="Resource guards for file/payload/collection size limits",
    )

    if max_file_size_precondition and max_file_mb is not None:
        max_bytes = int(max_file_mb * 1024 * 1024)
        # This validator typically checks a single param; we attach it for the first common one.
        preset.add_pre(max_file_size_precondition(file_param_names[0], max_bytes=max_bytes))

    if max_payload_size_precondition and max_payload_mb is not None:
        max_bytes = int(max_payload_mb * 1024 * 1024)
        preset.add_pre(max_payload_size_precondition(payload_param_names[0], max_bytes=max_bytes))

    if max_collection_size_precondition and max_items is not None:
        preset.add_pre(max_collection_size_precondition(collection_param_names[0], max_items=max_items))

    return preset


def basic_param_contracts(
    required_fields: Optional[Sequence[str]] = None,
    type_checks: Optional[Dict[str, type]] = None,
    max_lengths: Optional[Dict[str, int]] = None,
) -> ValidationPreset:
    """
    Minimal parameter contract preset (optional):
    - Required fields presence
    - Type checks for selected fields
    - Max length checks for selected fields

    This is intentionally simple; complex validation belongs to user models (e.g., Pydantic),
    while FailCore focuses on deterministic enforcement + traceable errors.
    """
    preset = ValidationPreset(
        name="basic_param_contracts",
        description="Basic param presence/type/length checks (lightweight)",
    )

    if required_fields_precondition and required_fields:
        preset.add_pre(required_fields_precondition(*list(required_fields)))

    if type_check_precondition and type_checks:
        for field_name, expected_type in type_checks.items():
            preset.add_pre(type_check_precondition(field_name, expected_type, required=False))

    if max_length_precondition and max_lengths:
        for field_name, limit in max_lengths.items():
            preset.add_pre(max_length_precondition(field_name, max_length=int(limit)))

    return preset


def output_contract(
    expected_kind: Optional[str] = None,
    schema: Optional[Dict[str, Any]] = None,
    strict: bool = False,
) -> ValidationPreset:
    """
    Output contract preset (optional):
    - Attaches output contract postcondition

    expected_kind: "JSON" | "TEXT" (case-insensitive)
    """
    preset = ValidationPreset(
        name="output_contract",
        description="Output contract validation (postcondition)",
    )

    if not output_contract_postcondition or not ExpectedKind:
        return preset

    kind_enum = None
    if expected_kind:
        ek = expected_kind.strip().upper()
        if ek == "JSON":
            kind_enum = ExpectedKind.JSON
        elif ek == "TEXT":
            kind_enum = ExpectedKind.TEXT

    preset.add_post(
        output_contract_postcondition(
            expected_kind=kind_enum,
            schema=schema,
            strict_mode=bool(strict),
        )
    )
    return preset


def combined_safe(
    strict: bool = True,
    sandbox_root: Optional[str] = None,
    allowed_domains: Optional[Sequence[str]] = None,
    max_file_mb: Optional[float] = None,
    max_payload_mb: Optional[float] = None,
    url_params: Sequence[str] = _DEFAULT_URL_PARAM_NAMES,
    path_params: Sequence[str] = _DEFAULT_PATH_PARAM_NAMES,
) -> ValidationPreset:
    """
    Combined safety preset for agent-style usage:
    - Filesystem sandbox protection
    - Network SSRF protection (optional allowlist)
    - Resource limits (optional)

    strict:
      - If True, enable stronger defaults (block internal networks, forbid userinfo)
      - Note: actual "block vs warn" is decided by ValidationResult severity mapping in your validator system
    """
    preset = ValidationPreset(
        name="combined_safe",
        description="Filesystem + network + optional resource guards (agent-friendly defaults)",
    )

    # Filesystem sandbox
    preset.preconditions.extend(
        fs_safe_sandbox(sandbox_root=sandbox_root, path_params=path_params).preconditions
    )

    # Network SSRF protection
    preset.preconditions.extend(
        net_safe(
            allowlist=allowed_domains,
            url_params=url_params,
            block_internal=True,
            allowed_schemes={"http", "https"},
            allowed_ports={80, 443},
            forbid_userinfo=bool(strict),
        ).preconditions
    )

    # Optional resource limits
    if max_file_mb is not None or max_payload_mb is not None:
        preset.preconditions.extend(
            resource_limits(
                max_file_mb=max_file_mb,
                max_payload_mb=max_payload_mb,
                max_items=None,
            ).preconditions
        )

    return preset


__all__ = [
    "ValidationPreset",
    "fs_safe_sandbox",
    "net_safe",
    "resource_limits",
    "basic_param_contracts",
    "output_contract",
    "combined_safe",
]
