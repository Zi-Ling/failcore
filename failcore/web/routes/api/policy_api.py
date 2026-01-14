# failcore/web/route/api/policy.py
"""
Policy management API endpoints
"""

from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, List
import traceback

from failcore.core.validate.registry import get_global_registry
from failcore.core.validate.bootstrap import auto_register
from failcore.core.validate.loader import (
    get_policy_dir,
    ensure_policy_files,
    load_policy,
    load_merged_policy,
    dump_policy,
    save_policy,
)
from failcore.core.validate.contracts import Policy, EnforcementMode
from failcore.core.validate.engine import ValidationEngine
from failcore.core.validate.contracts.v1.context import ContextV1


router = APIRouter(prefix="/api/policy", tags=["policy"])


@router.get("/validators")
async def list_validators() -> Dict[str, Any]:
    """List all available validators"""
    try:
        auto_register()
        registry = get_global_registry()
        validators = registry.list_validators()
        
        result = []
        for validator in validators:
            description = validator.__class__.__doc__ or ""
            description = description.split("\n")[0].strip()
            result.append({
                'id': validator.id,
                'domain': validator.domain,
                'description': description,
                'config_schema': validator.config_schema
            })
        
        return {
            'validators': result,
            'total': len(result)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            'error': str(e),
            'traceback': traceback.format_exc()
        })


@router.post("/init")
async def init_policy() -> Dict[str, Any]:
    """Initialize policy directory"""
    try:
        policy_dir = ensure_policy_files()
        return {
            'success': True,
            'policy_dir': str(policy_dir),
            'files': ['active.yaml', 'shadow.yaml', 'breakglass.yaml']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            'error': str(e),
            'traceback': traceback.format_exc()
        })


@router.get("/show/{policy_type}")
async def show_policy(policy_type: str, format: str = "yaml") -> Dict[str, Any]:
    """Show policy content"""
    try:
        policy_dir = get_policy_dir()
        
        if policy_type == 'merged':
            policy = load_merged_policy()
        else:
            if policy_type not in ['active', 'shadow', 'breakglass']:
                raise HTTPException(status_code=400, detail={'error': 'Invalid policy type'})
            
            policy_file = policy_dir / f"{policy_type}.yaml"
            if not policy_file.exists():
                raise HTTPException(status_code=404, detail={
                    'error': f'Policy file not found: {policy_file}',
                    'hint': 'Run init first'
                })
            
            policy = load_policy(policy_file)
        
        content = dump_policy(policy, format=format)
        
        return {
            'policy_type': policy_type,
            'format': format,
            'content': content,
            'policy': policy.model_dump()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            'error': str(e),
            'traceback': traceback.format_exc()
        })


@router.post("/save/{policy_type}")
async def save_policy_file(policy_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Save policy file"""
    try:
        if policy_type not in ['active', 'shadow', 'breakglass']:
            raise HTTPException(status_code=400, detail={'error': 'Invalid policy type'})
        
        if not data:
            raise HTTPException(status_code=400, detail={'error': 'No data provided'})
        
        # Parse policy
        policy = Policy(**data)
        
        # Save to file
        policy_dir = get_policy_dir()
        policy_file = policy_dir / f"{policy_type}.yaml"
        save_policy(policy, policy_file)
        
        return {
            'success': True,
            'policy_type': policy_type,
            'file': str(policy_file)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            'error': str(e),
            'traceback': traceback.format_exc()
        })


@router.post("/generate-shadow")
async def generate_shadow() -> Dict[str, Any]:
    """Generate shadow.yaml from active.yaml"""
    try:
        policy_dir = get_policy_dir()
        active_file = policy_dir / "active.yaml"
        shadow_file = policy_dir / "shadow.yaml"
        
        if not active_file.exists():
            raise HTTPException(status_code=404, detail={
                'error': 'active.yaml not found',
                'hint': 'Run init first'
            })
        
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
        
        return {
            'success': True,
            'file': str(shadow_file)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            'error': str(e),
            'traceback': traceback.format_exc()
        })


@router.post("/validate-file")
async def validate_file(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a policy file"""
    try:
        if not data:
            raise HTTPException(status_code=400, detail={'error': 'No data provided'})
        
        # Parse policy
        policy = Policy(**data)
        
        return {
            'valid': True,
            'version': policy.version,
            'validators_count': len(policy.validators),
            'metadata': policy.metadata
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


@router.post("/explain")
async def explain(data: Dict[str, Any]) -> Dict[str, Any]:
    """Explain what validators would trigger for a tool call"""
    try:
        if not data:
            raise HTTPException(status_code=400, detail={'error': 'No data provided'})
        
        tool = data.get('tool')
        params = data.get('params', {})
        
        if not tool:
            raise HTTPException(status_code=400, detail={'error': 'tool is required'})
        
        # Load merged policy
        policy = load_merged_policy()
        
        # Create context
        context = ContextV1(
            tool=tool,
            params=params,
            metadata={}
        )
        
        # Run validation
        auto_register()
        engine = ValidationEngine()
        decisions = engine.evaluate(context, policy)
        
        # Format results
        results = []
        for decision in decisions:
            results.append({
                'code': decision.code,
                'message': decision.message,
                'validator_id': decision.validator_id,
                'enforcement': decision.enforcement,
                'allowed': decision.allowed,
                'evidence': decision.evidence
            })
        
        # Calculate summary
        blocked = sum(1 for d in decisions if d.enforcement == "BLOCK" and not d.allowed)
        warned = sum(1 for d in decisions if d.enforcement == "WARN")
        shadowed = sum(1 for d in decisions if d.enforcement == "SHADOW")
        
        return {
            'tool': tool,
            'params': params,
            'decisions': results,
            'summary': {
                'blocked': blocked,
                'warnings': warned,
                'shadowed': shadowed,
                'total': len(results)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            'error': str(e),
            'traceback': traceback.format_exc()
        })


@router.post("/diff")
async def diff_policies(data: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two policies"""
    try:
        if not data:
            raise HTTPException(status_code=400, detail={'error': 'No data provided'})
        
        policy1_data = data.get('policy1')
        policy2_data = data.get('policy2')
        
        if not policy1_data or not policy2_data:
            raise HTTPException(status_code=400, detail={
                'error': 'Both policy1 and policy2 are required'
            })
        
        policy1 = Policy(**policy1_data)
        policy2 = Policy(**policy2_data)
        
        # Compare validators
        validators1 = set(policy1.validators.keys())
        validators2 = set(policy2.validators.keys())
        
        added = list(validators2 - validators1)
        removed = list(validators1 - validators2)
        common = validators1 & validators2
        
        # Check modified validators
        modified = []
        for vid in common:
            if policy1.validators[vid] != policy2.validators[vid]:
                modified.append({
                    'id': vid,
                    'before': policy1.validators[vid],
                    'after': policy2.validators[vid]
                })
        
        return {
            'added': added,
            'removed': removed,
            'modified': modified,
            'unchanged': list(common - {m['id'] for m in modified})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            'error': str(e),
            'traceback': traceback.format_exc()
        })
