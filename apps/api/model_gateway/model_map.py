# Mapping of internal model IDs to direct provider details and LiteLLM paths
MODEL_MAP = {
    # Pool models
    "openai_fast": {
        "provider": "openai",
        "provider_model_id": "gpt-4o-mini",
        "litellm_model": "openai/gpt-4o-mini"
    },
    "openai_premium": {
        "provider": "openai",
        "provider_model_id": "gpt-4o",
        "litellm_model": "openai/gpt-4o"
    },
    "anthropic_reasoning": {
        "provider": "anthropic",
        "provider_model_id": "claude-3-5-sonnet-20240620",
        "litellm_model": "anthropic/claude-3-5-sonnet-20240620"
    },
    "gemini_general": {
        "provider": "gemini",
        "provider_model_id": "gemini-2.0-flash",
        "litellm_model": "gemini/gemini-2.0-flash"
    },
    "gemini_pro": {
        "provider": "gemini",
        "provider_model_id": "gemini-2.5-pro-preview-06-05",
        "litellm_model": "gemini/gemini-2.5-pro-preview-06-05"
    },
    "groq_fast": {
        "provider": "groq",
        "provider_model_id": "llama-3.3-70b-versatile",
        "litellm_model": "groq/llama-3.3-70b-versatile"
    },
    "deepinfra_reasoning": {
        "provider": "deepinfra",
        "provider_model_id": "meta-llama/Llama-3.3-70B-Instruct",
        "litellm_model": "deepinfra/meta-llama/Llama-3.3-70B-Instruct"
    },
    "together_general": {
        "provider": "together",
        "provider_model_id": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "litellm_model": "together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
    },
    "fireworks_general": {
        "provider": "fireworks",
        "provider_model_id": "accounts/fireworks/models/llama-v3p1-8b-instruct",
        "litellm_model": "fireworks_ai/accounts/fireworks/models/llama-v3p1-8b-instruct"
    },
    "perplexity_search": {
        "provider": "perplexity",
        "provider_model_id": "sonar-reasoning",
        "litellm_model": "perplexity/sonar-reasoning"
    },
    "xai_grok": {
        "provider": "xai",
        "provider_model_id": "grok-2",
        "litellm_model": "xai/grok-2"
    },
    "mistral_large": {
        "provider": "mistral",
        "provider_model_id": "mistral-large-latest",
        "litellm_model": "mistral/mistral-large-latest"
    },
    "openrouter_fallback": {
        "provider": "openrouter",
        "provider_model_id": "openai/gpt-4o-mini",
        "litellm_model": "openrouter/openai/gpt-4o-mini"
    },
    
    # Backward compatible registry mappings
    "gpt4o-mini": {
        "provider": "openai",
        "provider_model_id": "gpt-4o-mini",
        "litellm_model": "openai/gpt-4o-mini"
    },
    "gpt4o-deep": {
        "provider": "openai",
        "provider_model_id": "gpt-4o",
        "litellm_model": "openai/gpt-4o"
    },
    "claude-sonnet": {
        "provider": "anthropic",
        "provider_model_id": "claude-3-5-sonnet-20240620",
        "litellm_model": "anthropic/claude-3-5-sonnet-20240620"
    },
    "claude-haiku": {
        "provider": "anthropic",
        "provider_model_id": "claude-3-haiku-20240307",
        "litellm_model": "anthropic/claude-3-haiku-20240307"
    },
    "gemini-2-flash": {
        "provider": "gemini",
        "provider_model_id": "gemini-2.0-flash",
        "litellm_model": "gemini/gemini-2.0-flash"
    },
    "gemini-2-5-pro": {
        "provider": "gemini",
        "provider_model_id": "gemini-2.5-pro-preview-06-05",
        "litellm_model": "gemini/gemini-2.5-pro-preview-06-05"
    },
    "groq-llama-3-3": {
        "provider": "groq",
        "provider_model_id": "llama-3.3-70b-versatile",
        "litellm_model": "groq/llama-3.3-70b-versatile"
    },
    "mistral-large": {
        "provider": "mistral",
        "provider_model_id": "mistral-large-latest",
        "litellm_model": "mistral/mistral-large-latest"
    },
    "deepseek-r1": {
        "provider": "openrouter",
        "provider_model_id": "deepseek/deepseek-r1",
        "litellm_model": "openrouter/deepseek/deepseek-r1"
    },
    "router-smart": {
        "provider": "openrouter",
        "provider_model_id": "router",
        "litellm_model": "openrouter/router"
    },
    "router-deep": {
        "provider": "openrouter",
        "provider_model_id": "auto",
        "litellm_model": "openrouter/auto"
    },
}
