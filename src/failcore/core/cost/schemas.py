# failcore/core/cost/schemas.py
"""
Pydantic Schema Validators - Optional safety net for cost extraction

Lightweight validation:
- Type checking (mypy support)
- Auto documentation (IDE hints)
- Optional validation (strict in dev, lenient in prod)
- <5% performance overhead

Usage:
    # Register with validator
    ProviderMetadata(
        provider="openai",
        version="v1",
        extraction_rule=openai_rule,
        validator=OpenAIUsageV1,  # Optional safety net
    )
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class BaseUsageSchema(BaseModel):
    """Base schema for all usage models"""
    model_config = ConfigDict(
        extra='allow',  # Allow extra fields (lenient)
        validate_assignment=False,  # Skip validation on assignment (performance)
    )


class OpenAIUsageV1(BaseUsageSchema):
    """
    OpenAI API v1 usage schema
    
    Ref: https://platform.openai.com/docs/api-reference/chat/object
    """
    prompt_tokens: int = Field(ge=0, description="Number of tokens in prompt")
    completion_tokens: int = Field(ge=0, description="Number of tokens in completion")
    total_tokens: int = Field(ge=0, description="Total tokens used")
    
    # Optional fields (newer models)
    prompt_tokens_details: Optional[dict] = Field(None, description="Prompt token breakdown")
    completion_tokens_details: Optional[dict] = Field(None, description="Completion token breakdown")


class AnthropicUsageLatest(BaseUsageSchema):
    """
    Anthropic Claude API usage schema
    
    Ref: https://docs.anthropic.com/claude/reference/messages_post
    """
    input_tokens: int = Field(ge=0, description="Number of input tokens")
    output_tokens: int = Field(ge=0, description="Number of output tokens")
    
    # Optional cache fields
    cache_creation_input_tokens: Optional[int] = Field(None, ge=0, description="Cache creation tokens")
    cache_read_input_tokens: Optional[int] = Field(None, ge=0, description="Cache read tokens")


class GoogleUsageLatest(BaseUsageSchema):
    """
    Google Gemini API usage schema
    
    Ref: https://ai.google.dev/api/rest/v1/UsageMetadata
    """
    promptTokenCount: int = Field(ge=0, description="Prompt tokens")
    candidatesTokenCount: int = Field(ge=0, description="Candidate tokens")
    totalTokenCount: int = Field(ge=0, description="Total tokens")


class GenericUsage(BaseUsageSchema):
    """
    Generic fallback schema
    
    Accepts common token field variations
    """
    # Input tokens (various names)
    input_tokens: Optional[int] = Field(None, ge=0)
    prompt_tokens: Optional[int] = Field(None, ge=0)
    request_tokens: Optional[int] = Field(None, ge=0)
    
    # Output tokens (various names)
    output_tokens: Optional[int] = Field(None, ge=0)
    completion_tokens: Optional[int] = Field(None, ge=0)
    response_tokens: Optional[int] = Field(None, ge=0)
    
    # Total (optional)
    total_tokens: Optional[int] = Field(None, ge=0)
    
    # Cost (if provided)
    cost_usd: Optional[float] = Field(None, ge=0.0)


__all__ = [
    "BaseUsageSchema",
    "OpenAIUsageV1",
    "AnthropicUsageLatest",
    "GoogleUsageLatest",
    "GenericUsage",
]
