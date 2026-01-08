# failcore/core/cost/providers.py
"""
Provider Configurations - Declarative metadata for mainstream providers

Auto-registers on module import for zero-config usage.

Supported providers:
- OpenAI (v1)
- Anthropic (latest)
- Google Gemini (latest)
- Generic fallback

Future: Load from YAML/JSON for hot-reload support
"""

from .metadata import ProviderMetadata, ExtractionRule, FieldMapping, FieldType
from .schemas import OpenAIUsageV1, AnthropicUsageLatest, GoogleUsageLatest, GenericUsage
from .registry import get_default_registry


# =====================================================
# OpenAI
# =====================================================

OPENAI_V1_RULE = ExtractionRule(
    paths=[
        "usage",
        "choices[0].message.usage",
        "response.usage",
        "data.usage",
    ],
    field_mappings=[
        # OpenAI uses prompt_tokens/completion_tokens, but also support input_tokens/output_tokens
        FieldMapping("prompt_tokens", "input_tokens", FieldType.INT, optional=True),
        FieldMapping("completion_tokens", "output_tokens", FieldType.INT, optional=True),
        # Also support direct input_tokens/output_tokens (for compatibility)
        FieldMapping("input_tokens", "input_tokens", FieldType.INT, optional=True),
        FieldMapping("output_tokens", "output_tokens", FieldType.INT, optional=True),
        FieldMapping("total_tokens", "total_tokens", FieldType.INT, optional=True),
        # Cost and metadata
        FieldMapping("cost_usd", "cost_usd", FieldType.FLOAT, optional=True),
        FieldMapping("model", "model", FieldType.STRING, optional=True),
        FieldMapping("provider", "provider", FieldType.STRING, optional=True),
        # Optional fields
        FieldMapping("prompt_tokens_details", "input_tokens_details", FieldType.ANY, optional=True),
        FieldMapping("completion_tokens_details", "output_tokens_details", FieldType.ANY, optional=True),
    ],
    requires_all=[],  # Make flexible - either prompt_tokens or input_tokens is acceptable
)

OPENAI_V1 = ProviderMetadata(
    provider="openai",
    version="v1",
    extraction_rule=OPENAI_V1_RULE,
    estimated=False,  # Provider-reported
    validator=OpenAIUsageV1,
    aliases=["gpt", "chatgpt"],
)


# =====================================================
# Anthropic (Claude)
# =====================================================

ANTHROPIC_LATEST_RULE = ExtractionRule(
    paths=[
        "usage",
        "response.usage",
        "data.usage",
        "content.usage",
    ],
    field_mappings=[
        FieldMapping("input_tokens", "input_tokens", FieldType.INT),
        FieldMapping("output_tokens", "output_tokens", FieldType.INT),
        # Cache fields (optional)
        FieldMapping("cache_creation_input_tokens", "cache_creation_input_tokens", FieldType.INT, optional=True, default=0),
        FieldMapping("cache_read_input_tokens", "cache_read_input_tokens", FieldType.INT, optional=True, default=0),
    ],
    requires_all=["input_tokens", "output_tokens"],
)

ANTHROPIC_LATEST = ProviderMetadata(
    provider="anthropic",
    version="latest",
    extraction_rule=ANTHROPIC_LATEST_RULE,
    estimated=False,  # Provider-reported
    validator=AnthropicUsageLatest,
    aliases=["claude", "claude-3"],
)


# =====================================================
# Google Gemini
# =====================================================

GOOGLE_LATEST_RULE = ExtractionRule(
    paths=[
        "usage",
        "usageMetadata",
        "response.usage",
        "response.usageMetadata",
    ],
    field_mappings=[
        # Google uses camelCase
        FieldMapping("promptTokenCount", "input_tokens", FieldType.INT),
        FieldMapping("candidatesTokenCount", "output_tokens", FieldType.INT),
        FieldMapping("totalTokenCount", "total_tokens", FieldType.INT),
        # Also support snake_case variants
        FieldMapping("prompt_token_count", "input_tokens", FieldType.INT, optional=True),
        FieldMapping("candidates_token_count", "output_tokens", FieldType.INT, optional=True),
        FieldMapping("total_token_count", "total_tokens", FieldType.INT, optional=True),
        # Cost and metadata
        FieldMapping("cost_usd", "cost_usd", FieldType.FLOAT, optional=True),
        FieldMapping("model", "model", FieldType.STRING, optional=True),
        FieldMapping("provider", "provider", FieldType.STRING, optional=True),
    ],
    requires_all=["input_tokens", "output_tokens"],
)

GOOGLE_LATEST = ProviderMetadata(
    provider="google",
    version="latest",
    extraction_rule=GOOGLE_LATEST_RULE,
    estimated=False,  # Provider-reported
    validator=GoogleUsageLatest,
    aliases=["gemini", "palm"],
)


# =====================================================
# Cohere
# =====================================================

COHERE_LATEST_RULE = ExtractionRule(
    paths=[
        "usage",
        "meta.tokens",
        "response.meta.tokens",
    ],
    field_mappings=[
        FieldMapping("input_tokens", "input_tokens", FieldType.INT, optional=True),
        FieldMapping("output_tokens", "output_tokens", FieldType.INT, optional=True),
        FieldMapping("prompt_tokens", "input_tokens", FieldType.INT, optional=True),
        FieldMapping("response_tokens", "output_tokens", FieldType.INT, optional=True),
        FieldMapping("total_tokens", "total_tokens", FieldType.INT, optional=True),
        # Cost and metadata
        FieldMapping("cost_usd", "cost_usd", FieldType.FLOAT, optional=True),
        FieldMapping("model", "model", FieldType.STRING, optional=True),
        FieldMapping("provider", "provider", FieldType.STRING, optional=True),
    ],
    requires_all=[],
)

COHERE_LATEST = ProviderMetadata(
    provider="cohere",
    version="latest",
    extraction_rule=COHERE_LATEST_RULE,
    estimated=False,
    validator=GenericUsage,
    aliases=["command"],
)


# =====================================================
# Mistral
# =====================================================

MISTRAL_LATEST_RULE = ExtractionRule(
    paths=[
        "usage",
        "response.usage",
    ],
    field_mappings=[
        FieldMapping("prompt_tokens", "input_tokens", FieldType.INT),
        FieldMapping("completion_tokens", "output_tokens", FieldType.INT),
        FieldMapping("total_tokens", "total_tokens", FieldType.INT),
        # Cost and metadata
        FieldMapping("cost_usd", "cost_usd", FieldType.FLOAT, optional=True),
        FieldMapping("model", "model", FieldType.STRING, optional=True),
        FieldMapping("provider", "provider", FieldType.STRING, optional=True),
    ],
    requires_all=["input_tokens", "output_tokens"],
)

MISTRAL_LATEST = ProviderMetadata(
    provider="mistral",
    version="latest",
    extraction_rule=MISTRAL_LATEST_RULE,
    estimated=False,
    validator=GenericUsage,
    aliases=["mistralai"],
)


# =====================================================
# Chinese LLM Providers
# =====================================================

# ZhipuAI (GLM)
ZHIPU_LATEST_RULE = ExtractionRule(
    paths=[
        "usage",
        "data.usage",
    ],
    field_mappings=[
        FieldMapping("prompt_tokens", "input_tokens", FieldType.INT, optional=True),
        FieldMapping("completion_tokens", "output_tokens", FieldType.INT, optional=True),
        FieldMapping("total_tokens", "total_tokens", FieldType.INT, optional=True),
    ],
    requires_all=[],
)

ZHIPU_LATEST = ProviderMetadata(
    provider="zhipu",
    version="latest",
    extraction_rule=ZHIPU_LATEST_RULE,
    estimated=False,
    validator=GenericUsage,
    aliases=["zhipuai", "glm", "chatglm"],
)

# Baidu (ERNIE)
BAIDU_LATEST_RULE = ExtractionRule(
    paths=[
        "usage",
        "result.usage",
    ],
    field_mappings=[
        FieldMapping("prompt_tokens", "input_tokens", FieldType.INT, optional=True),
        FieldMapping("completion_tokens", "output_tokens", FieldType.INT, optional=True),
        FieldMapping("total_tokens", "total_tokens", FieldType.INT, optional=True),
    ],
    requires_all=[],
)

BAIDU_LATEST = ProviderMetadata(
    provider="baidu",
    version="latest",
    extraction_rule=BAIDU_LATEST_RULE,
    estimated=False,
    validator=GenericUsage,
    aliases=["ernie", "wenxin"],
)

# Aliyun (Qwen)
ALIYUN_LATEST_RULE = ExtractionRule(
    paths=[
        "usage",
        "output.usage",
    ],
    field_mappings=[
        FieldMapping("input_tokens", "input_tokens", FieldType.INT, optional=True),
        FieldMapping("output_tokens", "output_tokens", FieldType.INT, optional=True),
        FieldMapping("total_tokens", "total_tokens", FieldType.INT, optional=True),
    ],
    requires_all=[],
)

ALIYUN_LATEST = ProviderMetadata(
    provider="aliyun",
    version="latest",
    extraction_rule=ALIYUN_LATEST_RULE,
    estimated=False,
    validator=GenericUsage,
    aliases=["qwen", "tongyi"],
)

# Tencent (Hunyuan)
TENCENT_LATEST_RULE = ExtractionRule(
    paths=[
        "usage",
        "Usage",
    ],
    field_mappings=[
        FieldMapping("PromptTokens", "input_tokens", FieldType.INT, optional=True),
        FieldMapping("CompletionTokens", "output_tokens", FieldType.INT, optional=True),
        FieldMapping("TotalTokens", "total_tokens", FieldType.INT, optional=True),
    ],
    requires_all=[],
)

TENCENT_LATEST = ProviderMetadata(
    provider="tencent",
    version="latest",
    extraction_rule=TENCENT_LATEST_RULE,
    estimated=False,
    validator=GenericUsage,
    aliases=["hunyuan"],
)


# =====================================================
# Generic Fallback
# =====================================================

GENERIC_RULE = ExtractionRule(
    paths=[
        "usage",
        "result.usage",
        "response.usage",
        "meta.usage",
        "data.usage",
        "payload.usage",
        "_usage",
    ],
    field_mappings=[
        # Input tokens (try all variants - priority order matters for mapping)
        FieldMapping("input_tokens", "input_tokens", FieldType.INT, optional=True),
        FieldMapping("prompt_tokens", "input_tokens", FieldType.INT, optional=True),
        FieldMapping("request_tokens", "input_tokens", FieldType.INT, optional=True),
        # Output tokens (try all variants)
        FieldMapping("output_tokens", "output_tokens", FieldType.INT, optional=True),
        FieldMapping("completion_tokens", "output_tokens", FieldType.INT, optional=True),
        FieldMapping("response_tokens", "output_tokens", FieldType.INT, optional=True),
        # Total
        FieldMapping("total_tokens", "total_tokens", FieldType.INT, optional=True),
        # Cost (if available)
        FieldMapping("cost_usd", "cost_usd", FieldType.FLOAT, optional=True),
        # Model/Provider (preserve if present)
        FieldMapping("model", "model", FieldType.STRING, optional=True),
        FieldMapping("provider", "provider", FieldType.STRING, optional=True),
    ],
    requires_all=[],  # No required fields (best-effort)
)

GENERIC = ProviderMetadata(
    provider="generic",
    version="latest",
    extraction_rule=GENERIC_RULE,
    estimated=True,  # Usually estimated
    validator=GenericUsage,
    aliases=["unknown", "fallback"],
)


# =====================================================
# Auto-register all providers
# =====================================================

def register_all_providers():
    """Register all built-in providers to default registry"""
    registry = get_default_registry()
    
    # Mainstream international providers
    registry.register(OPENAI_V1)
    registry.register(ANTHROPIC_LATEST)
    registry.register(GOOGLE_LATEST)
    registry.register(COHERE_LATEST)
    registry.register(MISTRAL_LATEST)
    
    # Chinese LLM providers
    registry.register(ZHIPU_LATEST)
    registry.register(BAIDU_LATEST)
    registry.register(ALIYUN_LATEST)
    registry.register(TENCENT_LATEST)
    
    # Generic fallback (lowest priority)
    registry.register(GENERIC)


# Auto-register on import
register_all_providers()


__all__ = [
    # International providers
    "OPENAI_V1",
    "ANTHROPIC_LATEST",
    "GOOGLE_LATEST",
    "COHERE_LATEST",
    "MISTRAL_LATEST",
    # Chinese providers
    "ZHIPU_LATEST",
    "BAIDU_LATEST",
    "ALIYUN_LATEST",
    "TENCENT_LATEST",
    # Fallback
    "GENERIC",
    # Registry
    "register_all_providers",
]
