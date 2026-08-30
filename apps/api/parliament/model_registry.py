from typing import List, Literal, Optional, Set
import database
from models import UserProviderKey
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from config import settings

class ModelInfo(BaseModel):
    id: str = Field(..., description="The unique identifier for the model")
    display_name: str
    provider: str
    litellm_model: str
    capabilities: Set[str] = Field(default_factory=set)
    tier: Literal["standard", "advanced"] = "standard"
    cost_tier: Literal["low", "medium", "high"]
    latency_class: Literal["fast", "normal", "slow"]
    quality_tier: Literal["baseline", "advanced", "flagship"]
    safety_profile: Literal["strict", "normal", "experimental"]
    enabled: bool = True
    recommended: bool = False
    tags: Optional[List[str]] = None
    logo_url: Optional[str] = None
    persona_type: Optional[str] = None
    persona_tagline: Optional[str] = None
    description: Optional[str] = None

ALL_MODELS: List[ModelInfo] = [
    ModelInfo(id="router-smart", display_name="Free Smart Router (OpenRouter)", provider="openrouter", litellm_model="openrouter/openrouter/free", capabilities={"chat","routing","tools"}, tier="standard", cost_tier="low", latency_class="fast", quality_tier="advanced", safety_profile="normal", recommended=True, logo_url="/logos/openrouter.svg"),
    ModelInfo(id="router-deep", display_name="GLM 5.2 Free (OpenRouter)", provider="openrouter", litellm_model="openrouter/z-ai/glm-5.2:free", capabilities={"chat","routing","reasoning","tools"}, tier="advanced", cost_tier="low", latency_class="normal", quality_tier="advanced", safety_profile="normal", logo_url="/logos/openrouter.svg"),
    ModelInfo(id="gpt4o-mini", display_name="GPT-4o Mini (OpenAI)", provider="openai", litellm_model="openai/gpt-4o-mini", capabilities={"chat","tools","vision"}, tier="standard", cost_tier="low", latency_class="fast", quality_tier="baseline", safety_profile="strict", logo_url="/logos/openai.svg"),
    ModelInfo(id="gpt4o-deep", display_name="GPT-4o (OpenAI)", provider="openai", litellm_model="openai/gpt-4o", capabilities={"chat","tools","vision","reasoning"}, tier="advanced", cost_tier="high", latency_class="normal", quality_tier="flagship", safety_profile="strict", logo_url="/logos/openai.svg", persona_type="The Methodical Analyst", persona_tagline="Precision through structured reasoning", description="Legacy durable preset; runtime health decides availability"),
    ModelInfo(id="claude-sonnet", display_name="Claude 3.5 Sonnet (Anthropic)", provider="anthropic", litellm_model="anthropic/claude-3-5-sonnet-20240620", capabilities={"chat","tools","vision","reasoning"}, tier="advanced", cost_tier="medium", latency_class="normal", quality_tier="flagship", safety_profile="strict", logo_url="/logos/claude.svg", persona_type="The Thoughtful Mentor", persona_tagline="Nuanced insight with ethical care", description="Legacy durable preset; runtime health decides availability"),
    ModelInfo(id="claude-haiku", display_name="Claude 3 Haiku (Anthropic)", provider="anthropic", litellm_model="anthropic/claude-3-haiku-20240307", capabilities={"chat","tools"}, tier="standard", cost_tier="low", latency_class="fast", quality_tier="baseline", safety_profile="strict", logo_url="/logos/claude.svg"),
    ModelInfo(id="gemini-2-flash", display_name="Gemini 3.7 Flash", provider="gemini", litellm_model="gemini/gemini-3.7-flash", capabilities={"chat","tools","vision","long_context"}, tier="standard", cost_tier="low", latency_class="fast", quality_tier="advanced", safety_profile="normal", logo_url="/logos/googlegemini.svg", description="Current Gemini workhorse model; account pricing/limits apply"),
    ModelInfo(id="gemini-2-5-pro", display_name="Gemini 3.7 Flash (legacy Pro preset)", provider="gemini", litellm_model="gemini/gemini-3.7-flash", capabilities={"chat","tools","vision","long_context","reasoning"}, tier="advanced", cost_tier="medium", latency_class="normal", quality_tier="advanced", safety_profile="normal", logo_url="/logos/googlegemini.svg", persona_type="The Cold Logician", persona_tagline="Ruthless precision, zero sentiment"),
    ModelInfo(id="groq-llama-3-3", display_name="GPT-OSS 20B (Groq)", provider="groq", litellm_model="groq/openai/gpt-oss-20b", capabilities={"chat","tools","reasoning"}, tier="standard", cost_tier="low", latency_class="fast", quality_tier="advanced", safety_profile="normal", logo_url="/logos/groq.svg", persona_type="The Creative Visionary", persona_tagline="Fast open-weight reasoning"),
    ModelInfo(id="llama-3-free", display_name="GPT-OSS 20B (OpenRouter Free)", provider="openrouter", litellm_model="openrouter/openai/gpt-oss-20b:free", capabilities={"chat","tools","reasoning"}, tier="standard", cost_tier="low", latency_class="fast", quality_tier="advanced", safety_profile="normal", logo_url="/logos/openrouter.svg"),
    ModelInfo(id="mimo-v2-free", display_name="GPT-OSS 20B (OpenRouter Free legacy)", provider="openrouter", litellm_model="openrouter/openai/gpt-oss-20b:free", capabilities={"chat","reasoning"}, tier="standard", cost_tier="low", latency_class="fast", quality_tier="advanced", safety_profile="normal", logo_url="/logos/openrouter.svg"),
    ModelInfo(id="openrouter-nemotron-free", display_name="Nemotron 3 Super (OpenRouter Free)", provider="openrouter", litellm_model="openrouter/nvidia/nemotron-3-super-120b-a12b:free", capabilities={"chat","tools","reasoning"}, tier="advanced", cost_tier="low", latency_class="normal", quality_tier="advanced", safety_profile="normal", logo_url="/logos/openrouter.svg"),
    ModelInfo(id="mistral-large", display_name="Mistral Large", provider="mistral", litellm_model="mistral/mistral-large-latest", capabilities={"chat","tools","reasoning"}, tier="advanced", cost_tier="medium", latency_class="normal", quality_tier="flagship", safety_profile="normal", logo_url="/logos/mistralai.svg", persona_type="The European Pragmatist", persona_tagline="Efficient solutions, minimal waste"),
    ModelInfo(id="deepseek-r1", display_name="DeepSeek R1", provider="openrouter", litellm_model="openrouter/deepseek/deepseek-r1", capabilities={"chat","reasoning"}, tier="advanced", cost_tier="medium", latency_class="normal", quality_tier="flagship", safety_profile="normal", logo_url="/logos/deepseek.svg", persona_type="The Deep Thinker", persona_tagline="Chain-of-thought reasoning at scale"),
    # Current frontier/SOTA roster, all routed through OpenRouter's unified API.
    ModelInfo(id="sota-gpt", display_name="GPT-5.6 Sol", provider="openrouter", litellm_model="openrouter/openai/gpt-5.6-sol", capabilities={"chat","tools","vision","reasoning"}, tier="advanced", cost_tier="high", latency_class="normal", quality_tier="flagship", safety_profile="strict", recommended=True, logo_url="/logos/openai.svg", persona_type="The Systems Architect", persona_tagline="Frontier reasoning and synthesis"),
    ModelInfo(id="sota-claude", display_name="Claude Opus 5", provider="openrouter", litellm_model="openrouter/anthropic/claude-opus-5", capabilities={"chat","tools","vision","reasoning"}, tier="advanced", cost_tier="high", latency_class="normal", quality_tier="flagship", safety_profile="strict", logo_url="/logos/claude.svg", persona_type="The Critical Thinker", persona_tagline="Deep analysis and long-horizon judgment"),
    ModelInfo(id="sota-gemini", display_name="Gemini 3.1 Pro Preview", provider="openrouter", litellm_model="openrouter/google/gemini-3.1-pro-preview", capabilities={"chat","tools","vision","reasoning","long_context"}, tier="advanced", cost_tier="high", latency_class="normal", quality_tier="flagship", safety_profile="normal", logo_url="/logos/googlegemini.svg", persona_type="The Context Engine", persona_tagline="Long-context multimodal analysis"),
    ModelInfo(id="sota-grok", display_name="Grok 4.6", provider="openrouter", litellm_model="openrouter/x-ai/grok-4.6", capabilities={"chat","tools","reasoning","vision"}, tier="advanced", cost_tier="high", latency_class="normal", quality_tier="flagship", safety_profile="normal", logo_url="/logos/xai.svg", persona_type="The Contrarian", persona_tagline="Alternative hypotheses and adversarial reasoning"),
    ModelInfo(id="sota-glm", display_name="GLM-5", provider="openrouter", litellm_model="openrouter/z-ai/glm-5", capabilities={"chat","tools","reasoning"}, tier="advanced", cost_tier="medium", latency_class="normal", quality_tier="flagship", safety_profile="normal", logo_url="/logos/zai.svg", persona_type="The Open-Weight Strategist", persona_tagline="Strong reasoning with efficient inference"),
    ModelInfo(id="sota-kimi", display_name="Kimi K2.5", provider="openrouter", litellm_model="openrouter/moonshotai/kimi-k2.5", capabilities={"chat","tools","vision","reasoning"}, tier="advanced", cost_tier="medium", latency_class="normal", quality_tier="flagship", safety_profile="normal", logo_url="/logos/moonshot.svg", persona_type="The Researcher", persona_tagline="Broad synthesis and technical exploration"),
]

FREE_ARENA_MODELS: List[str] = ["router-smart", "router-deep", "llama-3-free", "openrouter-nemotron-free"]
SOTA_ARENA_MODELS: List[str] = ["sota-gpt", "sota-claude", "sota-gemini", "sota-grok", "sota-glm", "sota-kimi"]
ARENA_MODELS: List[str] = FREE_ARENA_MODELS

def _provider_enabled(provider: str) -> bool:
    if settings.USE_MOCK:
        return True
    provider_keys = {
        "openrouter": ("OPENROUTER_API_KEY",),
        "openai": ("OPENAI_API_KEY",),
        "anthropic": ("ANTHROPIC_API_KEY",),
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "groq": ("GROQ_API_KEY",),
        "mistral": ("MISTRAL_API_KEY",),
        "perplexity": ("PERPLEXITY_API_KEY",),
        "xai": ("XAI_API_KEY",),
        "deepinfra": ("DEEPINFRA_API_KEY",),
        "together": ("TOGETHERAI_API_KEY", "TOGETHER_API_KEY"),
        "fireworks": ("FIREWORKS_API_KEY",),
    }
    names = provider_keys.get(provider, (f"{provider.upper()}_API_KEY",))
    return any(bool(getattr(settings, name, None)) for name in names)

def list_enabled_models() -> List[ModelInfo]:
    return [m for m in ALL_MODELS if m.enabled and _provider_enabled(m.provider)]

def list_enabled_models_for_user(user_id: Optional[str] = None) -> List[ModelInfo]:
    enabled_models = list_enabled_models()
    if not user_id: return enabled_models
    user_providers = set()
    try:
        with Session(database.engine) as session:
            stmt = select(UserProviderKey.provider).where(UserProviderKey.user_id == user_id)
            user_providers = set(session.exec(stmt).all())
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to fetch BYOK for user {user_id}: {e}")
    enabled_ids = {m.id for m in enabled_models}
    for model in ALL_MODELS:
        if model.enabled and model.id not in enabled_ids and model.provider in user_providers:
            enabled_models.append(model); enabled_ids.add(model.id)
    return enabled_models

def get_model_info(name: str) -> Optional[ModelInfo]:
    return next((model for model in ALL_MODELS if model.id == name), None)

def resolve_model_info(model_key: str) -> Optional[ModelInfo]:
    direct = get_model_info(model_key)
    if direct is not None: return direct
    from model_gateway.model_map import MODEL_MAP, ModelKeyError, resolve_model_key
    try:
        canonical_key = resolve_model_key(model_key)
        litellm_model = MODEL_MAP[canonical_key]["litellm_model"]
    except (KeyError, ModelKeyError, TypeError, ValueError):
        return None
    for model in ALL_MODELS:
        if model.litellm_model == litellm_model: return model
    return None

def get_default_model() -> ModelInfo:
    enabled = list_enabled_models()
    for model in enabled:
        if model.recommended: return model
    if enabled: return enabled[0]
    raise RuntimeError("No models are enabled; configure at least one provider API key.")

def get_model(model_id: str) -> ModelInfo:
    info = get_model_info(model_id)
    if not info: raise ValueError(f"Unknown model: {model_id}")
    return info

def get_arena_models() -> List[ModelInfo]:
    roster = FREE_ARENA_MODELS if getattr(settings, "FREE_ONLY_MODE", False) else SOTA_ARENA_MODELS
    enabled = {m.id for m in list_enabled_models()}
    return [info for model_id in roster if (info := get_model_info(model_id)) and model_id in enabled]
