"""
Policy management commands

Commands for working with validation policies:
- List available validators
- Generate shadow policy from active policy
- Apply breakglass overrides
- Show policy merge result
- Explain why a tool was blocked
"""

from pathlib import Path
import sys
import json

from ...core.validate.registry import get_global_registry
from ...core.validate.bootstrap import auto_register
from ...core.validate.loader import (
    get_policy_dir,
    ensure_policy_files,
    load_policy,
    load_merged_policy,
    dump_policy,
    save_policy,
)
from ...core.validate.contracts import Policy, EnforcementMode
from ...core.validate.engine import ValidationEngine
from ...core.validate.contracts.v1.context import ContextV1


def register_command(subparsers):
    """Register the 'policy' command and its subcommands"""
    policy_p = subparsers.add_parser("policy", help="Manage validation policies")
    policy_sub = policy_p.add_subparsers(dest="policy_command", help="Policy subcommands")
    
    # init
    init_p = policy_sub.add_parser("init", help="Initialize policy directory with default files")
    init_p.set_defaults(func=init_policy)
    
    # list-validators
    list_p = policy_sub.add_parser("list-validators", help="List all available validators")
    list_p.set_defaults(func=list_validators)
    
    # show
    show_p = policy_sub.add_parser("show", help="Show policy content")
    show_p.add_argument("--type", "-t", dest="policy_type",
                        choices=["active", "shadow", "breakglass", "merged"],
                        default="active",
                        help="Policy type to show")
    show_p.add_argument("--format", "-f", dest="output_format",
                        choices=["yaml", "json"],
                        default="yaml",
                        help="Output format")
    show_p.set_defaults(func=show_policy)
    
    # generate-shadow
    gen_p = policy_sub.add_parser("generate-shadow", 
                                  help="Generate shadow.yaml from active.yaml")
    gen_p.set_defaults(func=generate_shadow)
    
    # validate-file
    val_p = policy_sub.add_parser("validate-file", help="Validate a policy file")
    val_p.add_argument("policy_file", help="Path to policy file")
    val_p.set_defaults(func=validate_file)
    
    # explain
    exp_p = policy_sub.add_parser("explain", help="Explain what validators would trigger")
    exp_p.add_argument("--tool", "-t", required=True, help="Tool name")
    exp_p.add_argument("--param", "-p", action="append", default=[],
                       help="Parameter in key=value format (can be repeated)")
    exp_p.add_argument("--verbose", "-v", action="store_true",
                       help="Show detailed evidence and all decisions")
    exp_p.add_argument("--json", action="store_true",
                       help="Output as JSON")
    exp_p.set_defaults(func=explain)
    
    # diff
    diff_p = policy_sub.add_parser("diff", help="Show differences between two policy files")
    diff_p.add_argument("file1", help="First policy file")
    diff_p.add_argument("file2", help="Second policy file")
    diff_p.set_defaults(func=diff_policies)
    
    return policy_p


def init_policy(args):
    """Initialize policy directory with default files"""
    try:
        policy_dir = ensure_policy_files()
        print(f"[OK] Policy directory initialized: {policy_dir}")
        print("\nCreated files:")
        print("  - active.yaml    (main policy)")
        print("  - shadow.yaml    (observation mode)")
        print("  - breakglass.yaml (emergency overrides)")
        return 0
    except Exception as e:
        print(f"[ERROR] Failed to initialize: {e}", file=sys.stderr)
        return 1


def list_validators(args):
    """List all available validators"""
    try:
        auto_register()
        registry = get_global_registry()
        
        validators = registry.list_validators()
        
        if not validators:
            print("No validators registered")
            return 0
        
        print("Available Validators:")
        print("-" * 80)
        print(f"{'ID':<30} {'Domain':<15} {'Description':<35}")
        print("-" * 80)
        
        for validator in validators:
            description = validator.__class__.__doc__ or ""
            description = description.split("\n")[0].strip()
            description = description[:35]
            print(f"{validator.id:<30} {validator.domain:<15} {description:<35}")
        
        print("-" * 80)
        print(f"Total: {len(validators)} validators")
        return 0
        
    except Exception as e:
        print(f"✗ Failed to list validators: {e}", file=sys.stderr)
        return 1


def show_policy(args):
    """Show policy content"""
    try:
        policy_dir = get_policy_dir()
        policy_type = args.policy_type
        output_format = args.output_format
        
        if policy_type == "merged":
            policy = load_merged_policy()
        else:
            policy_file = policy_dir / f"{policy_type}.yaml"
            if not policy_file.exists():
                print(f"Policy file not found: {policy_file}")
                print("Run 'failcore policy init' first")
                return 1
            policy = load_policy(policy_file)
        
        content = dump_policy(policy, format=output_format)
        
        print(f"=== {policy_type.title()} Policy ===")
        print(content)
        return 0
        
    except Exception as e:
        print(f"✗ Failed to load policy: {e}", file=sys.stderr)
        return 1


def generate_shadow(args):
    """Generate shadow.yaml from active.yaml with all enforcements set to SHADOW"""
    try:
        policy_dir = get_policy_dir()
        active_file = policy_dir / "active.yaml"
        shadow_file = policy_dir / "shadow.yaml"
        
        if not active_file.exists():
            print("[ERROR] active.yaml not found", file=sys.stderr)
            print("Run 'failcore policy init' first")
            return 1
        
        # Load active policy
        active_policy = load_policy(active_file)
        
        # Convert to shadow mode
        shadow_policy_dict = active_policy.model_dump()
        
        # Set all enforcements to SHADOW
        if "validators" in shadow_policy_dict:
            for validator_id, validator_config in shadow_policy_dict["validators"].items():
                if isinstance(validator_config, dict):
                    validator_config["enforcement"] = "SHADOW"
        
        # Update metadata
        if "metadata" not in shadow_policy_dict:
            shadow_policy_dict["metadata"] = {}
        shadow_policy_dict["metadata"]["description"] = "Shadow mode policy (observation only)"
        shadow_policy_dict["metadata"]["derived_from"] = "active.yaml"
        
        # Save shadow policy
        shadow_policy = Policy(**shadow_policy_dict)
        save_policy(shadow_policy, shadow_file)
        
        print(f"[OK] Generated shadow.yaml from active.yaml")
        print(f"  All enforcements set to SHADOW mode")
        return 0
        
    except Exception as e:
        print(f"[ERROR] Failed to generate shadow policy: {e}", file=sys.stderr)
        return 1


def validate_file(args):
    """Validate a policy file"""
    try:
        policy = load_policy(Path(args.policy_file))
        print(f"[OK] Policy file is valid")
        
        # Show summary
        print(f"\nPolicy Summary:")
        print(f"  Version: {policy.version}")
        print(f"  Validators: {len(policy.validators)}")
        if policy.metadata:
            print(f"  Description: {policy.metadata.get('description', 'N/A')}")
        return 0
        
    except Exception as e:
        print(f"[ERROR] Invalid policy file: {e}", file=sys.stderr)
        return 1


def explain(args):
    """Explain what validators would trigger for a tool call"""
    try:
        # Parse parameters
        params = {}
        for p in args.param:
            if "=" in p:
                key, value = p.split("=", 1)
                params[key] = value
        
        # Load merged policy (active + shadow + breakglass)
        policy = load_merged_policy()
        
        # Create context
        context = ContextV1(
            tool=args.tool,
            params=params,
            metadata={}
        )
        
        # Run validation
        auto_register()
        engine = ValidationEngine(policy=policy)
        decisions = engine.evaluate(context)
        
        # Get triggered validators
        triggered_validators = list(set(d.validator_id for d in decisions))
        
        # Create explanation
        from failcore.core.validate.explain import explain_decisions
        explanation = explain_decisions(decisions, policy, triggered_validators)
        
        # Display results using enhanced explanation
        verbose = getattr(args, 'verbose', False)
        print(explanation.get_summary(verbose=verbose))
        
        # Print JSON output if requested
        if getattr(args, 'json', False):
            import json
            print("\n" + json.dumps(explanation.to_dict(), indent=2))
        
        return 0 if not explanation.is_blocked else 1
        
    except Exception as e:
        print(f"[ERROR] Failed to explain: {e}", file=sys.stderr)
        return 1


def diff_policies(args):
    """Show differences between two policy files"""
    try:
        policy1 = load_policy(Path(args.file1))
        policy2 = load_policy(Path(args.file2))
        
        print(f"\nComparing:")
        print(f"  {args.file1}")
        print(f"  {args.file2}\n")
        
        # Compare validators
        validators1 = set(policy1.validators.keys())
        validators2 = set(policy2.validators.keys())
        
        added = validators2 - validators1
        removed = validators1 - validators2
        common = validators1 & validators2
        
        if added:
            print(f"+ Added validators: {', '.join(added)}")
        if removed:
            print(f"- Removed validators: {', '.join(removed)}")
        
        # Check modified validators
        modified = []
        for vid in common:
            if policy1.validators[vid] != policy2.validators[vid]:
                modified.append(vid)
        
        if modified:
            print(f"~ Modified validators: {', '.join(modified)}")
        
        if not added and not removed and not modified:
            print("[OK] No differences in validators")
        
        return 0
        
    except Exception as e:
        print(f"[ERROR] Failed to diff policies: {e}", file=sys.stderr)
        return 1
