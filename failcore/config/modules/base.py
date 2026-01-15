# failcore/config/modules/base.py
"""
Base Module Configuration

Base class for all module configurations.
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class ModuleConfig:
    """
    Base configuration for all modules.
    
    Design principle:
    - enabled: Only determines if module is REGISTERED at startup
    - NOT used for runtime decision making
    - Each module has its own semantic configuration fields
    """
    
    enabled: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        result = {}
        for key, value in self.__dict__.items():
            if not key.startswith("_"):
                if isinstance(value, ModuleConfig):
                    result[key] = value.to_dict()
                elif isinstance(value, (dict, list, str, int, float, bool, type(None))):
                    result[key] = value
                else:
                    result[key] = str(value)
        return result
