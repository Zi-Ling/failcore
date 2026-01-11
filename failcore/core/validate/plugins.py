# failcore/core/validate/plugins.py
"""
Plugin System: Load external builtin via entry_points.

This module enables third-party builtin to be discovered and loaded
through Python entry_points mechanism.

Design principles:
- Plugins are optional (no hard dependencies)
- Plugins follow the same BaseValidator interface
- Plugins are isolated (failures don't crash core)
- Plugins are discoverable (via setuptools entry_points)

Entry point group: "failcore.builtin"

Example plugin setup.py:
```python
setup(
    name="my-failcore-plugin",
    entry_points={
        "failcore.builtin": [
            "my_validator = my_plugin:MyValidator",
        ],
    },
)
```
"""

from __future__ import annotations

from typing import List, Optional
import importlib.metadata
import logging

from .validator import BaseValidator
from .registry import ValidatorRegistry, get_global_registry


# Entry point group for builtin
VALIDATOR_ENTRY_POINT_GROUP = "failcore.builtin"

logger = logging.getLogger(__name__)


def discover_plugin_validators() -> List[BaseValidator]:
    """
    Discover plugin builtin via entry_points.
    
    Returns:
        List of validator instances from plugins
    
    Note:
        Plugins that fail to load are logged and skipped.
        This ensures core functionality isn't broken by bad plugins.
    """
    validators = []
    
    try:
        # Get all entry points for validator group
        entry_points = importlib.metadata.entry_points()
        
        # Handle different importlib.metadata APIs
        if hasattr(entry_points, 'select'):
            # Python 3.10+
            validator_eps = entry_points.select(group=VALIDATOR_ENTRY_POINT_GROUP)
        else:
            # Python 3.9
            validator_eps = entry_points.get(VALIDATOR_ENTRY_POINT_GROUP, [])
        
        for ep in validator_eps:
            try:
                # Load the entry point
                validator_cls = ep.load()
                
                # Instantiate if it's a class
                if isinstance(validator_cls, type):
                    validator = validator_cls()
                else:
                    validator = validator_cls
                
                # Verify it implements BaseValidator interface
                if not isinstance(validator, BaseValidator):
                    logger.warning(
                        f"Plugin validator '{ep.name}' from '{ep.value}' "
                        f"does not implement BaseValidator interface. Skipping."
                    )
                    continue
                
                validators.append(validator)
                logger.info(f"Loaded plugin validator: {validator.id} from {ep.value}")
                
            except Exception as e:
                logger.warning(
                    f"Failed to load plugin validator '{ep.name}' from '{ep.value}': {e}",
                    exc_info=True
                )
                continue
    
    except Exception as e:
        logger.error(f"Failed to discover plugin builtin: {e}", exc_info=True)
    
    return validators


def load_plugins(registry: Optional[ValidatorRegistry] = None) -> int:
    """
    Discover and register plugin builtin.
    
    Args:
        registry: Registry to register plugins to (if None, uses global registry)
    
    Returns:
        Number of plugins successfully loaded
    """
    if registry is None:
        registry = get_global_registry()
    
    validators = discover_plugin_validators()
    
    loaded_count = 0
    for validator in validators:
        try:
            registry.register(validator)
            loaded_count += 1
        except ValueError as e:
            # Validator already registered (probably built-in with same ID)
            logger.warning(f"Plugin validator '{validator.id}' conflicts with existing validator: {e}")
        except Exception as e:
            logger.error(f"Failed to register plugin validator '{validator.id}': {e}", exc_info=True)
    
    return loaded_count


def is_plugin_system_available() -> bool:
    """
    Check if plugin system is available.
    
    Returns:
        True if importlib.metadata is available
    """
    try:
        import importlib.metadata
        return True
    except ImportError:
        return False


class PluginValidator:
    """
    Example plugin validator for documentation purposes.
    
    To create a plugin validator:
    
    1. Implement BaseValidator interface:
    ```python
    from failcore.core.validate.validator import BaseValidator
    from failcore.core.validate.contracts.v1 import ContextV1, DecisionV1, ValidatorConfigV1
    
    class MyValidator(BaseValidator):
        @property
        def id(self) -> str:
            return "my_plugin_validator"
        
        @property
        def domain(self) -> str:
            return "custom"
        
        def evaluate(self, context: ContextV1, config: Optional[ValidatorConfigV1] = None) -> List[DecisionV1]:
            # Your validation logic here
            return []
    ```
    
    2. Register as entry point in setup.py:
    ```python
    setup(
        name="my-failcore-plugin",
        entry_points={
            "failcore.builtin": [
                "my_validator = my_plugin.builtin:MyValidator",
            ],
        },
    )
    ```
    
    3. Install and it will be auto-discovered:
    ```bash
    pip install my-failcore-plugin
    ```
    """
    pass


__all__ = [
    "discover_plugin_validators",
    "load_plugins",
    "is_plugin_system_available",
    "VALIDATOR_ENTRY_POINT_GROUP",
]
