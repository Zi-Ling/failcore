# failcore/cli/validate_cmd.py
"""
Trace validation command
"""

from pathlib import Path
from failcore.core.trace.validator import TraceValidator


def register_command(subparsers):
    """Register the 'validate' command and its arguments."""
    validate_p = subparsers.add_parser("validate", help="Validate trace file against v0.1.1 schemas")
    validate_p.add_argument("trace", help="Path to trace file")
    validate_p.set_defaults(func=validate_trace)


def validate_trace(args):
    """Validate trace file against v0.1.1 specification"""
    trace_path = args.trace
    
    if not Path(trace_path).exists():
        print(f"Error: File not found: {trace_path}")
        return 1
    
    print(f"Validating: {trace_path}")
    print(f"Schema: failcore.trace.v0.1.1")
    print()
    
    validator = TraceValidator()
    is_valid, errors = validator.validate_file(trace_path)
    
    if is_valid:
        print("[OK] Validation passed")
        print(f"  All events conform to spec")
        return 0
    else:
        print(f"[ERROR] Validation failed with {len(errors)} error(s)")
        print()
        
        # Group errors by code
        by_code = {}
        for err in errors:
            if err.code not in by_code:
                by_code[err.code] = []
            by_code[err.code].append(err)
        
        # Display errors grouped
        for code, errs in sorted(by_code.items()):
            print(f"[{code}] ({len(errs)} occurrence(s))")
            for err in errs[:3]:  # Show first 3 of each type
                print(f"  {err.format()}")
            if len(errs) > 3:
                print(f"  ... and {len(errs) - 3} more")
            print()
        
        return 1
