"""
Dynamic Price Provider

Flexible pricing engine supporting multiple sources:
- Hardcoded defaults
- Environment variables
- API calls (future)
- Custom providers
"""

from typing import Dict, Any, Optional, Protocol
from abc import ABC, abstractmethod
import os
import json


class PriceProvider(Protocol):
    """Protocol for price providers"""
    
    def get_price(
        self,
        model: str,
        token_type: str,  # "input" or "output"
    ) -> Optional[float]:
        """
        Get price per 1K tokens in USD
        
        Returns None if price not found
        """
        ...


class StaticPriceProvider:
    """
    Static hardcoded price provider
    
    Default fallback for known models
    """
    
    # Default pricing (USD per 1K tokens, as of 2024)
    DEFAULT_PRICING = {
        # OpenAI
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        
        # Anthropic
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3.5-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
        
        # Others
        "gemini-pro": {"input": 0.00025, "output": 0.0005},
        "llama-3-70b": {"input": 0.0007, "output": 0.0008},
    }
    
    def __init__(self, custom_pricing: Dict[str, Dict[str, float]] = None):
        """
        Args:
            custom_pricing: Override default pricing
        """
        self.pricing = custom_pricing or self.DEFAULT_PRICING
    
    def get_price(self, model: str, token_type: str) -> Optional[float]:
        """Get price for model and token type"""
        if model in self.pricing:
            return self.pricing[model].get(token_type)
        return None


class EnvPriceProvider:
    """
    Environment variable price provider
    
    Reads prices from environment variables:
    - FAILCORE_PRICE_GPT4_INPUT=0.03
    - FAILCORE_PRICE_GPT4_OUTPUT=0.06
    - FAILCORE_PRICE_CLAUDE3SONNET_INPUT=0.003
    """
    
    def __init__(self, prefix: str = "FAILCORE_PRICE_"):
        self.prefix = prefix
        self._cache: Dict[str, float] = {}
        self._load_prices()
    
    def _load_prices(self):
        """Load prices from environment variables"""
        for key, value in os.environ.items():
            if key.startswith(self.prefix):
                try:
                    # Parse: FAILCORE_PRICE_GPT4_INPUT -> (gpt-4, input)
                    parts = key[len(self.prefix):].lower().split('_')
                    if len(parts) >= 2:
                        token_type = parts[-1]  # input or output
                        model = '_'.join(parts[:-1]).replace('_', '-')
                        cache_key = f"{model}:{token_type}"
                        self._cache[cache_key] = float(value)
                except (ValueError, IndexError):
                    pass
    
    def get_price(self, model: str, token_type: str) -> Optional[float]:
        """Get price from environment"""
        cache_key = f"{model}:{token_type}"
        return self._cache.get(cache_key)


class JsonPriceProvider:
    """
    JSON file price provider
    
    Reads prices from JSON file:
    {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015}
    }
    """
    
    def __init__(self, json_path: str):
        self.json_path = json_path
        self.pricing: Dict[str, Dict[str, float]] = {}
        self._load_json()
    
    def _load_json(self):
        """Load pricing from JSON file"""
        try:
            with open(self.json_path, 'r') as f:
                self.pricing = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    
    def get_price(self, model: str, token_type: str) -> Optional[float]:
        """Get price from JSON"""
        if model in self.pricing:
            return self.pricing[model].get(token_type)
        return None


class ApiPriceProvider:
    """
    HTTP API price provider
    
    Fetches real-time pricing from remote API endpoint.
    
    Expected API response format:
    {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015}
    }
    
    Example:
        provider = ApiPriceProvider(
            api_url="https://pricing.example.com/api/prices",
            cache_ttl=3600,  # Cache for 1 hour
        )
    """
    
    def __init__(
        self,
        api_url: str,
        cache_ttl: int = 3600,  # Cache for 1 hour
        timeout: int = 5,  # Request timeout
        api_key: Optional[str] = None,
    ):
        """
        Args:
            api_url: URL to fetch pricing from
            cache_ttl: Cache time-to-live in seconds
            timeout: Request timeout in seconds
            api_key: Optional API key for authentication
        """
        self.api_url = api_url
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self.api_key = api_key
        
        # Cache
        self.pricing: Dict[str, Dict[str, float]] = {}
        self.last_fetch: Optional[float] = None
    
    def get_price(self, model: str, token_type: str) -> Optional[float]:
        """Get price from API (with caching)"""
        import time
        
        # Check if cache is valid
        now = time.time()
        if self.last_fetch is None or (now - self.last_fetch) > self.cache_ttl:
            self._fetch_prices()
        
        # Return from cache
        if model in self.pricing:
            return self.pricing[model].get(token_type)
        return None
    
    def _fetch_prices(self):
        """Fetch prices from API"""
        try:
            # Try to use requests if available
            try:
                import requests
                
                headers = {}
                if self.api_key:
                    headers['Authorization'] = f'Bearer {self.api_key}'
                
                response = requests.get(
                    self.api_url,
                    headers=headers,
                    timeout=self.timeout,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.pricing = data
                    import time
                    self.last_fetch = time.time()
            
            except ImportError:
                # Fallback to urllib if requests not available
                import urllib.request
                import time
                
                req = urllib.request.Request(self.api_url)
                if self.api_key:
                    req.add_header('Authorization', f'Bearer {self.api_key}')
                
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode())
                    self.pricing = data
                    self.last_fetch = time.time()
        
        except Exception:
            # On error, keep using cached prices
            pass
    
    def refresh(self):
        """Force refresh prices from API"""
        self.last_fetch = None
        self._fetch_prices()


class ChainedPriceProvider:
    """
    Chained price provider with fallback
    
    Tries providers in order until one returns a price
    
    Example:
        chain = ChainedPriceProvider([
            EnvPriceProvider(),      # Try env first
            JsonPriceProvider("prices.json"),  # Then JSON
            StaticPriceProvider(),   # Finally hardcoded defaults
        ])
    """
    
    def __init__(self, providers: list):
        """
        Args:
            providers: List of price providers (tried in order)
        """
        self.providers = providers
    
    def get_price(self, model: str, token_type: str) -> Optional[float]:
        """Get price from first provider that has it"""
        for provider in self.providers:
            price = provider.get_price(model, token_type)
            if price is not None:
                return price
        return None
    
    def add_provider(self, provider, position: int = 0):
        """Add provider at specific position (0 = highest priority)"""
        self.providers.insert(position, provider)


class DynamicPriceEngine:
    """
    Main dynamic price engine
    
    Facade for easy price lookups with automatic fallback chain
    """
    
    def __init__(
        self,
        provider: Optional[PriceProvider] = None,
        enable_env: bool = True,
        enable_json: bool = False,
        enable_api: bool = False,
        json_path: str = "prices.json",
        api_url: Optional[str] = None,
        api_cache_ttl: int = 3600,
    ):
        """
        Args:
            provider: Custom provider (overrides default chain)
            enable_env: Enable environment variable provider
            enable_json: Enable JSON file provider
            enable_api: Enable API price provider
            json_path: Path to JSON pricing file
            api_url: API endpoint URL
            api_cache_ttl: API cache TTL in seconds
        """
        if provider is not None:
            self.provider = provider
        else:
            # Build default chain (priority order)
            providers = []
            
            # 1. Environment variables (highest priority)
            if enable_env:
                providers.append(EnvPriceProvider())
            
            # 2. API provider (real-time updates)
            if enable_api and api_url:
                providers.append(ApiPriceProvider(
                    api_url=api_url,
                    cache_ttl=api_cache_ttl,
                ))
            
            # 3. JSON file
            if enable_json:
                providers.append(JsonPriceProvider(json_path))
            
            # 4. Static fallback (lowest priority)
            providers.append(StaticPriceProvider())
            
            self.provider = ChainedPriceProvider(providers)
    
    def get_price(
        self,
        model: str,
        token_type: str = "input"
    ) -> float:
        """
        Get price per 1K tokens
        
        Args:
            model: Model name (e.g., "gpt-4", "claude-3-sonnet")
            token_type: "input" or "output"
        
        Returns:
            Price in USD per 1K tokens (0.0 if not found)
        """
        price = self.provider.get_price(model, token_type)
        return price if price is not None else 0.0
    
    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Calculate total cost for token usage
        
        Returns:
            Total cost in USD
        """
        input_price = self.get_price(model, "input")
        output_price = self.get_price(model, "output")
        
        cost = (
            (input_tokens / 1000.0) * input_price +
            (output_tokens / 1000.0) * output_price
        )
        
        return cost


__all__ = [
    "PriceProvider",
    "StaticPriceProvider",
    "EnvPriceProvider",
    "JsonPriceProvider",
    "ApiPriceProvider",
    "ChainedPriceProvider",
    "DynamicPriceEngine",
]
