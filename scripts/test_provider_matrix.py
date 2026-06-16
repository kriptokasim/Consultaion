#!/usr/bin/env python3
import os
import sys
import time
import asyncio
from pathlib import Path

# Add apps/api to Python path
api_path = Path(__file__).resolve().parent.parent / "apps" / "api"
sys.path.insert(0, str(api_path))
os.chdir(str(api_path))

from config import settings
from model_gateway import export_api_keys
from parliament.model_registry import ALL_MODELS, list_enabled_models
from litellm import acompletion

# Map of test model strings for providers
TEST_MODELS = {
    "openai": "openai/gpt-4o-mini",
    "anthropic": "anthropic/claude-3-haiku-20240307",
    "gemini": "gemini/gemini-2.0-flash",
    "groq": "groq/llama-3.3-70b-versatile",
    "deepinfra": "deepinfra/meta-llama/Llama-3.3-70B-Instruct",
    "together": "together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    "fireworks": "fireworks_ai/accounts/fireworks/models/llama-v3p1-8b-instruct",
    "mistral": "mistral/mistral-large-latest",
    "xai": "xai/grok-2",
    "perplexity": "perplexity/sonar-reasoning",
    "openrouter": "openrouter/openai/gpt-4o-mini",
}

async def check_provider(provider: str) -> dict:
    provider = provider.lower()
    if provider not in TEST_MODELS:
        return {"success": False, "error": f"No diagnostic model mapped for {provider}", "latency_ms": 0}

    # Verify key exists
    if provider == "gemini":
        has_key = bool(settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY)
    else:
        has_key = bool(getattr(settings, f"{provider.upper()}_API_KEY", None))

    if not has_key:
        return {"success": False, "error": "API key is not configured in settings", "latency_ms": 0}

    model = TEST_MODELS[provider]
    start_ts = time.monotonic()
    try:
        # Perform low-latency diagnostic completion
        response = await acompletion(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
            timeout=10,
        )
        latency_ms = (time.monotonic() - start_ts) * 1000
        content = response.choices[0].message["content"] if response.choices else ""
        return {
            "success": True,
            "model": model,
            "response": content.strip().replace("\n", " "),
            "latency_ms": round(latency_ms, 2)
        }
    except Exception as e:
        latency_ms = (time.monotonic() - start_ts) * 1000
        return {
            "success": False,
            "error": str(e),
            "latency_ms": round(latency_ms, 2)
        }

async def main():
    print("=" * 60)
    print(" Consultaion Direct Provider Matrix Diagnostic Tool")
    print("=" * 60)

    # Ensure keys are exported to os.environ for LiteLLM
    export_api_keys()

    enabled_models = list_enabled_models()
    enabled_providers = sorted(list({m.provider for m in enabled_models}))
    all_providers = sorted(list({m.provider for m in ALL_MODELS}))

    print(f"Total defined providers in registry: {len(all_providers)}")
    print(f"Enabled providers with active configuration: {len(enabled_providers)}")
    print("-" * 60)

    tasks = {provider: check_provider(provider) for provider in all_providers}
    results = await asyncio.gather(*tasks.values())
    provider_results = dict(zip(tasks.keys(), results))

    print(f"{'Provider':<15} | {'Status':<10} | {'Latency (ms)':<12} | {'Message/Error'}")
    print("-" * 80)
    for provider, res in provider_results.items():
        if res["success"]:
            status_str = "\033[92mPASS\033[0m"
            latency_str = f"{res['latency_ms']:.2f}"
            detail_str = f"Model: {res['model']} -> Response: '{res['response']}'"
        else:
            if "API key is not configured" in res["error"]:
                status_str = "\033[93mMISSING\033[0m"
            else:
                status_str = "\033[91mFAIL\033[0m"
            latency_str = "N/A"
            detail_str = res["error"]

        print(f"{provider:<15} | {status_str:<19} | {latency_str:<12} | {detail_str}")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
