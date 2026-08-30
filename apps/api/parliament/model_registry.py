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
    ModelInfo(id="gpt4o-deep", display_name="GPT-4o (OpenAI)", provider="openai", litellm_model="openai/gpt-4o", capabilities={"chat","tools","vision","reasoning"}, tier="advanced", cost_tier="high", latency_class="normal", quality_tier="flagship", safety_profile="strict", logo_url="/logos/openai.svg", persona_type="The Methodical Analyst", persona_tagline="Precision through structured reasoning", description="Best for complex reasoning, coding, and multi-step analysis"),
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
]

# Default Arena is deliberately free-first. Paid presets remain selectable when
# their credentials are healthy, but the default experience must not require a
# paid OpenAI/Anthropic balance just to answer a user.
ARENA_MODELS: List[str] = ["groq-llama-3-3", "router-smart", "router-deep", "llama-3-free"]

def _provider_enabled(provider: str) -> bool:
    if settings.USE_MOCK:
        return True
    openrouter_available = bool(settings.OPENROUTER_API_KEY)
    if provider == "openrouter": return openrouter_available
    if provider == "openai": return bool(settings.OPENAI_API_KEY or openrouter_available)
    if provider == "anthropic": return bool(settings.ANTHROPIC_API_KEY or openrouter_available)
    if provider == "gemini": return bool(settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY or openrouter_available)
    if provider == "groq": return bool(settings.GROQ_API_KEY or openrouter_available)
    if provider == "mistral": return bool(settings.MISTRAL_API_KEY or openrouter_available)
    return False

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
    enabled = {m.id for m in list_enabled_models()}
    return [info for model_id in ARENA_MODELS if (info := get_model_info(model_id)) and model_id in enabled]
