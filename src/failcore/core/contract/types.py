# failcore/core/contract/types.py
"""
Contract types and enums - Core semantic definitions
"""

from enum import Enum


class ExpectedKind(Enum):
    """Expected output kinds for contract validation"""
    JSON = "json"
    TEXT = "text"
    FILE = "file"
    BINARY = "binary"
    NULL = "null"


class DriftType(Enum):
    """Types of contract drift that can be detected"""
    OUTPUT_KIND_MISMATCH = "output_kind_mismatch"
    INVALID_JSON = "invalid_json"
    SCHEMA_MISMATCH = "schema_mismatch"
    MISSING_REQUIRED_FIELDS = "missing_required_fields"
    TYPE_CONSTRAINT_VIOLATION = "type_constraint_violation"


class Decision(Enum):
    """Contract validation decision"""
    OK = "ok"           # Contract satisfied
    WARN = "warn"       # Drift detected but non-critical
    BLOCK = "block"     # Critical violation, should halt

