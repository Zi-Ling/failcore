# failcore/core/trace/validator.py
"""
Trace validator with multi-version support (v0.1.1+)
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class ValidationError:
    """Validation error with line number and details"""
    line: int
    code: str
    message: str
    suggestion: Optional[str] = None
    
    def format(self) -> str:
        """Format error for display"""
        parts = [f"Line {self.line}: [{self.code}] {self.message}"]
        if self.suggestion:
            parts.append(f"  Suggestion: {self.suggestion}")
        return "\n".join(parts)


class TraceValidator:
    """
    Validator for FailCore trace files with multi-version support
    
    Validates:
    - Schema version (auto-detected from event)
    - Required fields
    - Field types and enums
    - Timestamp format
    - Sequence monotonicity
    - STEP_START/END pairing
    - Attempt validity
    - depends_on references
    
    Version Support:
    - Write: v0.1.2 only (current)
    - Read: v0.1.1 (legacy), v0.1.2 (current)
    """
    
    # Schema version whitelist mapping (security: prevent path traversal)
    SCHEMA_MAP = {
        "failcore.trace.v0.1.1": "failcore.trace.v0.1.1.schema.json",
        "failcore.trace.v0.1.2": "failcore.trace.v0.1.2.schema.json",
        "failcore.trace.v0.1.3": "failcore.trace.v0.1.3.schema.json",
    }
    
    # Current write version
    CURRENT_SCHEMA_VERSION = "failcore.trace.v0.1.3"
    
    VALID_LEVELS = {"DEBUG", "INFO", "WARN", "ERROR"}
    VALID_EVENT_TYPES = {
        "RUN_START", "RUN_END",
        "STEP_START", "STEP_END",
        "FINGERPRINT_COMPUTED",
        "REPLAY_HIT", "REPLAY_MISS",
        "CONTRACT_DRIFT",  # v0.1.2+
        "VALIDATION_FAILED",
        "POLICY_DENIED",
        "OUTPUT_NORMALIZED",
        "ARTIFACT_WRITTEN",
        "SIDE_EFFECT_APPLIED"
    }
    VALID_STATUSES = {"ok", "fail", "blocked", "skipped", "replayed"}  # TraceStepStatus values
    VALID_PHASES = {"validate", "policy", "execute", "commit", "replay", "normalize"}
    
    def __init__(self):
        self.errors: List[ValidationError] = []
        self.last_seq: Dict[str, int] = {}  # run_id -> last seq
        self.step_starts: Dict[Tuple[str, str], int] = {}  # (run_id, step_id) -> line
        self.step_ends: Dict[Tuple[str, str], int] = {}
        self.all_step_ids: Dict[str, set] = {}  # run_id -> set of step_ids
        self.detected_versions: Dict[str, str] = {}  # run_id -> detected schema version
    
    def validate_file(self, path: str) -> Tuple[bool, List[ValidationError]]:
        """
        Validate a trace file
        
        Returns:
            (is_valid, errors)
        """
        self.errors = []
        self.last_seq = {}
        self.step_starts = {}
        self.step_ends = {}
        self.all_step_ids = {}
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        event = json.loads(line)
                        self._validate_event(event, line_num)
                    except json.JSONDecodeError as e:
                        self.errors.append(ValidationError(
                            line=line_num,
                            code="INVALID_JSON",
                            message=f"Invalid JSON: {e}",
                            suggestion="Ensure line contains valid JSON"
                        ))
        except FileNotFoundError:
            self.errors.append(ValidationError(
                line=0,
                code="FILE_NOT_FOUND",
                message=f"File not found: {path}",
            ))
            return False, self.errors
        
        # Check for unpaired steps
        self._validate_step_pairing()
        
        return len(self.errors) == 0, self.errors
    
    def _validate_event(self, event: Dict[str, Any], line: int):
        """Validate a single event"""
        # Check top-level required fields
        for field in ["schema", "seq", "ts", "level", "event", "run"]:
            if field not in event:
                self.errors.append(ValidationError(
                    line=line,
                    code="MISSING_FIELD",
                    message=f"Missing required field: {field}",
                    suggestion=f"Add '{field}' field at top level"
                ))
                return
        
        # Validate schema version with whitelist mapping (security: prevent path traversal)
        schema_version = event.get("schema", "")
        run_spec_version = event.get("run", {}).get("version", {}).get("spec", "")
        
        # Check against whitelist
        if schema_version not in self.SCHEMA_MAP:
            version_info = f"schema='{schema_version}'"
            if run_spec_version:
                version_info += f", run.version.spec='{run_spec_version}'"
            
            supported_versions = ", ".join(self.SCHEMA_MAP.keys())
            self.errors.append(ValidationError(
                line=line,
                code="UNKNOWN_SCHEMA",
                message=f"Unknown schema version ({version_info})",
                suggestion=f"Supported versions: {supported_versions}"
            ))
            return
        
        # Store detected version for this run
        run_id = event.get("run", {}).get("run_id", "unknown")
        if run_id not in self.detected_versions:
            self.detected_versions[run_id] = schema_version
        
        # Validate seq monotonicity
        run_id = event.get("run", {}).get("run_id", "unknown")
        seq = event.get("seq")
        if isinstance(seq, int):
            if seq < 1:
                self.errors.append(ValidationError(
                    line=line,
                    code="INVALID_SEQ",
                    message=f"Sequence must be >= 1, got {seq}",
                ))
            elif run_id in self.last_seq and seq <= self.last_seq[run_id]:
                self.errors.append(ValidationError(
                    line=line,
                    code="SEQ_NOT_MONOTONIC",
                    message=f"Sequence {seq} not greater than previous {self.last_seq[run_id]}",
                    suggestion="Sequence numbers must strictly increase"
                ))
            else:
                self.last_seq[run_id] = seq
        else:
            self.errors.append(ValidationError(
                line=line,
                code="INVALID_TYPE",
                message=f"Field 'seq' must be integer, got {type(seq).__name__}",
            ))
        
        # Validate timestamp
        try:
            datetime.fromisoformat(event["ts"].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            self.errors.append(ValidationError(
                line=line,
                code="INVALID_TIMESTAMP",
                message=f"Invalid ISO8601 timestamp: {event.get('ts')}",
                suggestion="Use format: YYYY-MM-DDTHH:MM:SS.ffffff+00:00"
            ))
        
        # Validate level
        if event["level"] not in self.VALID_LEVELS:
            self.errors.append(ValidationError(
                line=line,
                code="INVALID_LEVEL",
                message=f"Invalid level: {event['level']}",
                suggestion=f"Must be one of: {', '.join(self.VALID_LEVELS)}"
            ))
        
        # Validate event structure
        evt = event.get("event", {})
        evt_type = evt.get("type")
        if evt_type not in self.VALID_EVENT_TYPES:
            self.errors.append(ValidationError(
                line=line,
                code="INVALID_EVENT_TYPE",
                message=f"Invalid event type: {evt_type}",
                suggestion=f"Must be one of: {', '.join(sorted(self.VALID_EVENT_TYPES))}"
            ))
        
        # Validate run context
        run = event.get("run", {})
        if "run_id" not in run:
            self.errors.append(ValidationError(
                line=line,
                code="MISSING_RUN_ID",
                message="Missing run.run_id",
            ))
        if "created_at" not in run:
            self.errors.append(ValidationError(
                line=line,
                code="MISSING_RUN_CREATED_AT",
                message="Missing run.created_at",
            ))
        
        # Validate step-specific events
        if evt_type in ("STEP_START", "STEP_END", "POLICY_DENIED", "OUTPUT_NORMALIZED", "VALIDATION_FAILED"):
            self._validate_step_event(evt, run_id, evt_type, line)
        
        # Track step IDs
        if evt_type in ("STEP_START", "STEP_END"):
            step = evt.get("step", {})
            step_id = step.get("id")
            if step_id:
                if run_id not in self.all_step_ids:
                    self.all_step_ids[run_id] = set()
                self.all_step_ids[run_id].add(step_id)
    
    def _validate_step_event(self, evt: Dict[str, Any], run_id: str, evt_type: str, line: int):
        """Validate step-related event"""
        step = evt.get("step")
        if not step or not isinstance(step, dict):
            self.errors.append(ValidationError(
                line=line,
                code="MISSING_STEP",
                message=f"Event type {evt_type} requires 'step' object",
            ))
            return
        
        # Check step fields
        step_id = step.get("id")
        tool = step.get("tool")
        attempt = step.get("attempt", 1)
        
        if not step_id:
            self.errors.append(ValidationError(
                line=line,
                code="MISSING_STEP_ID",
                message="Missing step.id",
            ))
        if not tool:
            self.errors.append(ValidationError(
                line=line,
                code="MISSING_TOOL",
                message="Missing step.tool",
            ))
        
        if not isinstance(attempt, int) or attempt < 1:
            self.errors.append(ValidationError(
                line=line,
                code="INVALID_ATTEMPT",
                message=f"step.attempt must be integer >= 1, got {attempt}",
            ))
        
        # Track pairing
        key = (run_id, step_id)
        if evt_type == "STEP_START":
            if key in self.step_starts:
                self.errors.append(ValidationError(
                    line=line,
                    code="DUPLICATE_STEP_START",
                    message=f"Duplicate STEP_START for {step_id} (previous at line {self.step_starts[key]})",
                    suggestion="Each step should have only one STEP_START"
                ))
            self.step_starts[key] = line
        elif evt_type == "STEP_END":
            if key in self.step_ends:
                self.errors.append(ValidationError(
                    line=line,
                    code="DUPLICATE_STEP_END",
                    message=f"Duplicate STEP_END for {step_id} (previous at line {self.step_ends[key]})",
                ))
            self.step_ends[key] = line
        
        # Validate depends_on references
        depends_on = step.get("depends_on", [])
        if depends_on and run_id in self.all_step_ids:
            for dep in depends_on:
                if dep not in self.all_step_ids[run_id]:
                    self.errors.append(ValidationError(
                        line=line,
                        code="INVALID_DEPENDENCY",
                        message=f"step.depends_on references unknown step: {dep}",
                        suggestion="Ensure dependency step exists in trace"
                    ))
        
        # Validate STEP_END specific fields
        if evt_type == "STEP_END":
            data = evt.get("data", {})
            result = data.get("result", {})
            
            status = result.get("status")
            if status and status not in self.VALID_STATUSES:
                self.errors.append(ValidationError(
                    line=line,
                    code="INVALID_STATUS",
                    message=f"Invalid status: {status}",
                    suggestion=f"Must be one of: {', '.join(self.VALID_STATUSES)}"
                ))
            
            phase = result.get("phase")
            if phase and phase not in self.VALID_PHASES:
                self.errors.append(ValidationError(
                    line=line,
                    code="INVALID_PHASE",
                    message=f"Invalid phase: {phase}",
                    suggestion=f"Must be one of: {', '.join(self.VALID_PHASES)}"
                ))
    
    def _validate_step_pairing(self):
        """Check that all STEP_START have corresponding STEP_END"""
        for key in self.step_starts:
            if key not in self.step_ends:
                run_id, step_id = key
                self.errors.append(ValidationError(
                    line=self.step_starts[key],
                    code="UNPAIRED_STEP_START",
                    message=f"STEP_START at line {self.step_starts[key]} has no matching STEP_END for step {step_id}",
                    suggestion="Add STEP_END event for this step"
                ))
