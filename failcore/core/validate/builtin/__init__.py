# failcore/core/validate/builtin/base.py
"""
Validator implementations organized by category
"""

from .contract import (
    output_contract_postcondition,
    json_output_postcondition,
    text_output_postcondition,
)

from .security import (
    path_traversal_precondition,
)

from .type import (
    type_check_precondition,
    required_fields_precondition,
    max_length_precondition,
    pydantic_adapter_precondition,
)

from .network import (
    url_safe_precondition,
    domain_whitelist_precondition,
    internal_ip_block_precondition,
    port_range_precondition,
)

from .resource import (
    max_file_size_precondition,
    max_payload_size_precondition,
    max_collection_size_precondition,

)

__all__ = [
    # Contract builtin
    "output_contract_postcondition",
    "json_output_postcondition",
    "text_output_postcondition",
    
    # Security builtin
    "path_traversal_precondition",
    
    # Type builtin
    "type_check_precondition",
    "required_fields_precondition",
    "max_length_precondition",
    "pydantic_adapter_precondition",
    
    # Network builtin
    "url_safe_precondition",
    "domain_whitelist_precondition",
    "internal_ip_block_precondition",
    "port_range_precondition",
    
    # Resource builtin
    "max_file_size_precondition",
    "max_payload_size_precondition",
    "max_collection_size_precondition",
]

