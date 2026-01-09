# failcore/core/cost/pipeline.py
"""
Extraction Pipeline - Unified stages for all providers

Pipeline Flow:
1. PathFinder: Locate usage data in nested structures
2. TypeNormalizer: Convert values to expected types (safe_int, safe_float)
3. FieldMapper: Map provider fields to canonical CostUsage fields

Benefits:
- Eliminates 90% code duplication across extractors
- Easy to test each stage independently
- Composable for different provider needs
"""

from typing import Any, Optional, Dict, Tuple, List
from .metadata import ExtractionRule, FieldMapping, FieldType


class PathFinder:
    """
    Stage 1: Find usage data in nested structures
    
    Supports:
    - Nested attributes: "response.usage"
    - Array indexing: "choices[0].message.usage"
    - Dict keys: usage["prompt_tokens"]
    - Object attributes: response.usage
    """
    
    @staticmethod
    def find(data: Any, paths: List[str]) -> Tuple[Optional[Any], Optional[str]]:
        """
        Find usage data using priority-ordered paths
        
        Args:
            data: Source data (dict, object, etc.)
            paths: Priority-ordered list of paths
        
        Returns:
            Tuple of (found_data, successful_path)
        
        Examples:
            >>> PathFinder.find(response, ["usage", "data.usage"])
            ({"prompt_tokens": 10}, "usage")
        """
        for path in paths:
            result = PathFinder._traverse_path(data, path)
            if result is not None:
                return result, path
        
        return None, None
    
    @staticmethod
    def _traverse_path(data: Any, path: str) -> Optional[Any]:
        """
        Traverse a single path
        
        Supports:
        - "usage" → data.usage or data["usage"]
        - "data.usage" → data.data.usage
        - "choices[0].message" → data.choices[0].message
        """
        if not path:
            return data
        
        parts = path.split(".")
        current = data
        
        for part in parts:
            # Handle array indexing: "choices[0]"
            if "[" in part and "]" in part:
                key, index_str = part.split("[", 1)
                index_str = index_str.rstrip("]")
                
                try:
                    index = int(index_str)
                except ValueError:
                    return None
                
                # Navigate to array
                if key:
                    current = PathFinder._get_value(current, key)
                    if current is None:
                        return None
                
                # Index into array
                if isinstance(current, (list, tuple)):
                    if 0 <= index < len(current):
                        current = current[index]
                    else:
                        return None
                else:
                    return None
            else:
                # Simple attribute/key access
                current = PathFinder._get_value(current, part)
                if current is None:
                    return None
        
        return current
    
    @staticmethod
    def _get_value(obj: Any, key: str) -> Optional[Any]:
        """
        Get value from object by key (attribute or dict key)
        
        Priority:
        1. dict key
        2. object attribute
        """
        # Try dict key
        if isinstance(obj, dict):
            return obj.get(key)
        
        # Try object attribute
        if hasattr(obj, key):
            return getattr(obj, key, None)
        
        return None


class TypeNormalizer:
    """
    Stage 2: Normalize field types with safe conversion
    
    Handles:
    - None → default
    - String numbers → numeric types
    - Type mismatches → default (no exceptions)
    """
    
    @staticmethod
    def normalize(value: Any, field_type: FieldType, default: Any = None) -> Any:
        """
        Safely convert value to expected type
        
        Args:
            value: Input value
            field_type: Expected type
            default: Default value if conversion fails
        
        Returns:
            Converted value
        """
        if field_type == FieldType.INT:
            return TypeNormalizer.to_int(value, default or 0)
        elif field_type == FieldType.FLOAT:
            return TypeNormalizer.to_float(value, default or 0.0)
        elif field_type == FieldType.STRING:
            return TypeNormalizer.to_string(value, default or "")
        elif field_type == FieldType.BOOL:
            return TypeNormalizer.to_bool(value, default or False)
        else:  # FieldType.ANY
            return value if value is not None else default
    
    @staticmethod
    def to_int(value: Any, default: int = 0) -> int:
        """Safely convert to int"""
        if value is None:
            return default
        
        if isinstance(value, int):
            return value
        
        if isinstance(value, (float, str)):
            try:
                return int(float(value))
            except (ValueError, TypeError):
                return default
        
        # Try generic conversion
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def to_float(value: Any, default: float = 0.0) -> float:
        """Safely convert to float"""
        if value is None:
            return default
        
        if isinstance(value, float):
            return value
        
        if isinstance(value, (int, str)):
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        # Try generic conversion
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def to_string(value: Any, default: str = "") -> str:
        """Safely convert to string"""
        if value is None:
            return default
        return str(value)
    
    @staticmethod
    def to_bool(value: Any, default: bool = False) -> bool:
        """Safely convert to bool"""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)


class FieldMapper:
    """
    Stage 3: Map provider fields to canonical CostUsage fields
    
    Handles:
    - Field name mapping (prompt_tokens → input_tokens)
    - Required field validation
    - Optional fields with defaults
    - Object → dict conversion
    """
    
    @staticmethod
    def map_fields(
        usage_data: Any,
        field_mappings: List[FieldMapping],
        requires_all: Optional[List[str]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Map provider fields to canonical fields
        
        Args:
            usage_data: Usage data (dict or object)
            field_mappings: List of field mapping rules
            requires_all: Optional list of required target fields
        
        Returns:
            Tuple of (mapped_dict, error_reason)
        
        Examples:
            >>> FieldMapper.map_fields(
            ...     {"prompt_tokens": 10, "completion_tokens": 5},
            ...     [FieldMapping("prompt_tokens", "input_tokens", FieldType.INT)]
            ... )
            ({"input_tokens": 10}, None)
        """
        # Convert object to dict if needed
        if not isinstance(usage_data, dict):
            usage_data = FieldMapper._object_to_dict(usage_data)
            if not usage_data:
                return None, "usage_data_not_dict_or_object"
        
        # Map fields
        mapped = {}
        for mapping in field_mappings:
            source_value = usage_data.get(mapping.source)
            
            # Handle missing fields
            if source_value is None:
                if not mapping.optional:
                    # Required field missing
                    if requires_all and mapping.target in requires_all:
                        return None, f"required_field_missing: {mapping.source}"
                    # Not in requires_all, use default
                    if mapping.default is not None:
                        mapped[mapping.target] = mapping.default
                else:
                    # Optional field missing, use default
                    if mapping.default is not None:
                        mapped[mapping.target] = mapping.default
                continue
            
            # Normalize type
            normalized = TypeNormalizer.normalize(
                source_value,
                mapping.type,
                mapping.default
            )
            
            mapped[mapping.target] = normalized
        
        # Validate required fields
        if requires_all:
            missing = [f for f in requires_all if f not in mapped or mapped[f] is None]
            if missing:
                return None, f"required_fields_missing: {', '.join(missing)}"
        
        return mapped, None
    
    @staticmethod
    def _object_to_dict(obj: Any) -> Optional[Dict[str, Any]]:
        """Convert object to dict using __dict__ or common attributes"""
        if hasattr(obj, "__dict__"):
            result = vars(obj)
            if result:
                return result
        
        # Try extracting common cost/usage attributes
        result = {}
        common_attrs = [
            'prompt_tokens', 'completion_tokens', 'total_tokens',
            'input_tokens', 'output_tokens', 'cost_usd', 'model', 'provider',
            'cache_creation_input_tokens', 'cache_read_input_tokens',
            'reasoning_tokens', 'audio_tokens', 'cached_tokens',
        ]
        
        for attr in common_attrs:
            if hasattr(obj, attr):
                result[attr] = getattr(obj, attr)
        
        return result if result else None


class ExtractionPipeline:
    """
    Complete extraction pipeline: PathFinder → TypeNormalizer → FieldMapper
    
    Unified interface for all providers
    """
    
    @staticmethod
    def extract(
        data: Any,
        rule: ExtractionRule,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        """
        Run complete extraction pipeline
        
        Args:
            data: Source data (tool output)
            rule: Extraction rule
        
        Returns:
            Tuple of (extracted_dict, error_reason, successful_path)
        
        Examples:
            >>> ExtractionPipeline.extract(openai_response, openai_rule)
            ({"input_tokens": 10, "output_tokens": 5}, None, "usage")
        """
        # Stage 1: Find usage data
        usage_data, path = PathFinder.find(data, rule.paths)
        if usage_data is None:
            return None, "usage_not_found", None
        
        # Stage 2 + 3: Map and normalize fields
        mapped, error = FieldMapper.map_fields(
            usage_data,
            rule.field_mappings,
            rule.requires_all,
        )
        
        return mapped, error, path


__all__ = [
    "PathFinder",
    "TypeNormalizer",
    "FieldMapper",
    "ExtractionPipeline",
]
