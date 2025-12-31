"""
JSON Schema URL Resolver for FailCore

Provides stable URL-to-local-file mapping for $ref resolution in Draft-07 schemas.
Avoids relative path issues in pip packages and cross-platform environments.

Usage:
    from failcore.core.schemas.resolver import make_validator, load_schema
    
    # Create a validator with automatic $ref resolution
    validator = make_validator(schema)
    
    # Load a schema file with $ref support
    schema = load_schema("trace", "v0.1.2")
"""

from typing import Dict, Any, Optional, List
import json

try:
    from importlib.resources import files  # Python 3.9+
except ImportError:
    from importlib_resources import files  # Fallback for Python 3.7-3.8


# ============================================================================
# Schema Registry
# ============================================================================
# When adding a new schema version, add it to this list.
# The resolver will automatically load these schemas and use their $id as the URL key.

REGISTERED_SCHEMAS: List[str] = [
    # Common base definitions
    "common/failcore.common.base.v1.schema.json",
    
    # Trace schemas
    "trace/failcore.trace.v0.1.1.schema.json",
    "trace/failcore.trace.v0.1.2.schema.json",
    
    # Audit schemas
    "Audit/failcore.Audit.v0.1.1.schema.json",
]


# ============================================================================
# Module-level cache
# ============================================================================
# Cache loaded schemas to avoid repeated IO on every make_validator() call
_SCHEMA_STORE_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def _load_schema_file(relative_path: str) -> Dict[str, Any]:
    """
    Load a schema file from the schemas directory using importlib.resources.
    
    This works in all environments: source, wheel, zipimport, etc.
    
    Args:
        relative_path: Relative path from schemas root using POSIX separators
                      (e.g., "common/failcore.common.base.v1.schema.json")
    
    Returns:
        Parsed JSON schema as dict
    
    Raises:
        FileNotFoundError: If schema file not found or inaccessible
        json.JSONDecodeError: If schema is invalid JSON
    """
    try:
        # Use importlib.resources to access package data
        # This works even if the package is in a zip file
        schema_root = files("failcore.core.schemas")
        
        # Navigate using POSIX separators (works across all platforms)
        parts = relative_path.split("/")
        resource = schema_root
        for part in parts:
            resource = resource / part
        
        # Read the schema file
        content = resource.read_text(encoding="utf-8")
        return json.loads(content)
    
    except (FileNotFoundError, OSError, AttributeError) as e:
        # FileNotFoundError: file doesn't exist
        # OSError: file exists but can't be read (permissions, etc.)
        # AttributeError: importlib.resources API incompatibility
        raise FileNotFoundError(
            f"Schema file not found or inaccessible: {relative_path}. "
            f"Ensure the schema exists in failcore.core.schemas package."
        ) from e
    
    # Note: json.JSONDecodeError is NOT caught here - let it propagate
    # so callers can distinguish "file not found" from "invalid JSON"


def _load_registered_schemas() -> Dict[str, Dict[str, Any]]:
    """
    Load all registered schemas and build URL-to-schema store.
    
    Each schema's $id field becomes its canonical URL key for $ref resolution.
    Results are cached at module level for performance.
    
    Returns:
        Dict mapping $id URLs to loaded schema dicts
    
    Raises:
        RuntimeError: If any registered schema fails to load, lacks $id, or has duplicate $id
    """
    global _SCHEMA_STORE_CACHE
    
    # Return cached store if available
    if _SCHEMA_STORE_CACHE is not None:
        return _SCHEMA_STORE_CACHE
    
    store = {}
    id_to_path = {}  # Track which file each $id comes from
    
    for relative_path in REGISTERED_SCHEMAS:
        try:
            schema = _load_schema_file(relative_path)
            
            # Extract $id as the canonical URL
            schema_id = schema.get("$id")
            if not schema_id:
                raise RuntimeError(
                    f"Schema {relative_path} is missing required $id field. "
                    f"All registered schemas must have a stable $id URL."
                )
            
            # Detect duplicate $id (prevents silent overwrites)
            if schema_id in store:
                raise RuntimeError(
                    f"Duplicate schema $id detected: {schema_id}\n"
                    f"  First occurrence: {id_to_path[schema_id]}\n"
                    f"  Duplicate in: {relative_path}\n"
                    f"Each schema must have a unique $id URL."
                )
            
            store[schema_id] = schema
            id_to_path[schema_id] = relative_path
        
        except FileNotFoundError as e:
            raise RuntimeError(
                f"Registered schema not found: {relative_path}. "
                f"Check REGISTERED_SCHEMAS in resolver.py."
            ) from e
        
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Invalid JSON in registered schema: {relative_path}"
            ) from e
    
    # Cache the store for future calls
    _SCHEMA_STORE_CACHE = store
    return store


def get_resolver():
    """
    LEGACY API: Get a jsonschema RefResolver with FailCore schemas.
    
    ⚠️ WARNING: RefResolver is deprecated in jsonschema >= 4.18.
    For new code, use make_validator() instead.
    
    This function is kept for backward compatibility only.
    
    Returns:
        jsonschema.RefResolver instance (or None if jsonschema not installed)
    
    Example (legacy):
        from jsonschema import validate
        from failcore.core.schemas.resolver import get_resolver, load_schema
        
        schema = load_schema("trace", "v0.1.2")
        resolver = get_resolver()
        validate(instance=event, schema=schema, resolver=resolver)
    """
    try:
        from jsonschema import RefResolver
    except ImportError:
        return None
    
    # Load all registered schemas by $id
    store = _load_registered_schemas()
    
    # Create resolver with pre-populated store
    resolver = RefResolver(base_uri="", referrer={}, store=store)
    
    return resolver


def make_validator(schema: Dict[str, Any]):
    """
    Create a JSON Schema Draft-07 validator with automatic $ref resolution.
    
    This function adapts to the installed jsonschema version:
    - Modern versions (>= 4.18): Uses Registry API
    - Legacy versions (< 4.18): Uses RefResolver API
    
    All FailCore schemas are Draft-07, so we enforce Draft7Validator for consistency.
    
    Args:
        schema: The JSON schema to validate against (must be Draft-07)
    
    Returns:
        A Draft7Validator instance with $ref resolution
    
    Raises:
        ImportError: If jsonschema is not installed
        RuntimeError: If $ref resolution setup fails
    
    Example:
        from failcore.core.schemas.resolver import make_validator, load_schema
        
        schema = load_schema("trace", "v0.1.2")
        validator = make_validator(schema)
        
        try:
            validator.validate(event)
            print("Valid!")
        except Exception as e:
            print(f"Invalid: {e}")
    """
    try:
        from jsonschema import Draft7Validator
    except ImportError as e:
        raise ImportError(
            "jsonschema package is required for schema validation. "
            "Install it with: pip install jsonschema"
        ) from e
    
    # Load registered schemas for $ref resolution
    try:
        store = _load_registered_schemas()
    except RuntimeError as e:
        raise RuntimeError(
            f"Failed to load registered schemas: {e}. "
            f"This is a critical error for FailCore validation."
        ) from e
    
    # Use Draft7Validator (all FailCore schemas are Draft-07)
    ValidatorClass = Draft7Validator
    
    # Try modern Registry API first (jsonschema >= 4.18)
    try:
        from jsonschema import Registry
        
        # Create registry with our schemas
        registry = Registry().with_resources([
            (schema_id, schema_obj)
            for schema_id, schema_obj in store.items()
        ])
        
        # Create validator with registry
        return ValidatorClass(schema, registry=registry)
    
    except (ImportError, AttributeError):
        # Fall back to legacy RefResolver API (jsonschema < 4.18)
        try:
            from jsonschema import RefResolver
            
            resolver = RefResolver(base_uri="", referrer=schema, store=store)
            return ValidatorClass(schema, resolver=resolver)
        
        except Exception as e:
            # If both APIs fail, this is a critical error
            # FailCore is an Audit tool - we MUST NOT silently degrade $ref support
            raise RuntimeError(
                f"Failed to create validator with $ref resolution. "
                f"jsonschema version may be incompatible. Error: {e}"
            ) from e


def load_schema(schema_type: str, version: str) -> Dict[str, Any]:
    """
    Load a FailCore schema by type and version.
    
    Args:
        schema_type: Schema type ("trace", "Audit", "common")
        version: Schema version (e.g., "v0.1.2", "v1")
    
    Returns:
        Parsed JSON schema
    
    Raises:
        ValueError: If schema type/version is unknown
        FileNotFoundError: If schema file not found
    
    Example:
        schema = load_schema("trace", "v0.1.2")
        schema = load_schema("common", "v1")
    """
    # Map to relative path
    if schema_type == "common":
        relative_path = f"common/failcore.common.base.{version}.schema.json"
    elif schema_type == "trace":
        relative_path = f"trace/failcore.trace.{version}.schema.json"
    elif schema_type == "Audit":
        relative_path = f"Audit/failcore.Audit.{version}.schema.json"
    else:
        raise ValueError(f"Unknown schema type: {schema_type}")
    
    return _load_schema_file(relative_path)


def validate_event(event: Dict[str, Any], schema_type: str, version: str) -> Optional[str]:
    """
    Validate an event against a FailCore schema.
    
    Args:
        event: Event data to validate
        schema_type: Schema type ("trace", "Audit")
        version: Schema version (e.g., "v0.1.2")
    
    Returns:
        None if valid, error message string if invalid
    
    Note:
        Requires jsonschema package to be installed.
    
    Example:
        error = validate_event(trace_event, "trace", "v0.1.2")
        if error:
            print(f"Validation failed: {error}")
    """
    try:
        from jsonschema import ValidationError
        
        schema = load_schema(schema_type, version)
        validator = make_validator(schema)
        validator.validate(event)
        return None
    
    except ImportError:
        return "jsonschema package not installed (pip install jsonschema)"
    
    except ValidationError as e:
        return f"Validation error: {e.message}"
    
    except Exception as e:
        return f"Unexpected error: {str(e)}"


# Convenience exports
__all__ = [
    "get_resolver",       # LEGACY: Use make_validator() instead
    "make_validator",     # Recommended API
    "load_schema",
    "validate_event",
    "REGISTERED_SCHEMAS", # Schema registry (modify when adding new schemas)
]

