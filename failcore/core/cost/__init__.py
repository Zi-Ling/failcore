"""
Cost Guardrails

Economic safety: token/API cost tracking and budget enforcement

Features:
- Dynamic pricing engine (env, JSON, API sources)
- Streaming token watchdog (real-time budget enforcement)
- Burn rate limiting (spending velocity control)
- Multi-level alerts (80%/90%/95%/100% warnings)
"""

# Core models
from .models import CostUnit, CostUsage, Budget,BudgetScope

# Estimation and tracking
from .estimator import CostEstimator
from .tracker import CostTracker

# Dynamic pricing
from .pricing import (
    PriceProvider,
    StaticPriceProvider,
    EnvPriceProvider,
    JsonPriceProvider,
    ApiPriceProvider,
    ChainedPriceProvider,
    DynamicPriceEngine,
)

# Streaming control
from .streaming import (
    StreamingTokenWatchdog,
    StreamingCostGuard,
)

# Burn rate limiting
from .ratelimit import (
    BurnRateConfig,
    BurnRateLimiter,
)

# Budget alerts
from .alerts import (
    AlertLevel,
    BudgetAlert,
    BudgetAlertManager,
    SimpleAlertLogger,
)

# Global protection
from .guardian import (
    GuardianConfig,
    CostGuardian,
)

# Middleware
from .middleware import BudgetGuardMiddleware

# Usage extraction
from .usage import UsageExtractor

# Provider Metadata Registry (Phase C: Configuration-driven extraction)
from .registry import ProviderRegistry, get_default_registry
from .metadata import ProviderMetadata, ExtractionRule, FieldMapping, FieldType
from .pipeline import ExtractionPipeline, PathFinder, TypeNormalizer, FieldMapper

# Auto-register built-in providers
try:
    from . import providers  # noqa: F401  - Auto-registers all providers
except ImportError:
    pass

__all__ = [
    # Core models
    "CostUnit",
    "CostUsage",
    "Budget",
    "BudgetScope",
    # Estimation and tracking
    "CostEstimator",
    "CostTracker",
    # Dynamic pricing
    "PriceProvider",
    "StaticPriceProvider",
    "EnvPriceProvider",
    "JsonPriceProvider",
    "ApiPriceProvider",
    "ChainedPriceProvider",
    "DynamicPriceEngine",
    # Streaming control
    "StreamingTokenWatchdog",
    "StreamingCostGuard",
    # Burn rate limiting
    "BurnRateConfig",
    "BurnRateLimiter",
    # Budget alerts
    "AlertLevel",
    "BudgetAlert",
    "BudgetAlertManager",
    "SimpleAlertLogger",
    # Global protection
    "GuardianConfig",
    "CostGuardian",
    # Middleware
    "BudgetGuardMiddleware",
    # Usage extraction (unified API)
    "UsageExtractor",
    # Provider Metadata Registry (Phase C)
    "ProviderRegistry",
    "get_default_registry",
    "ProviderMetadata",
    "ExtractionRule",
    "FieldMapping",
    "FieldType",
    "ExtractionPipeline",
    "PathFinder",
    "TypeNormalizer",
    "FieldMapper",
]
