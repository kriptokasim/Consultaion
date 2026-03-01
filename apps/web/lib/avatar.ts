const ENABLE_DICEBEAR_AVATARS = process.env.NEXT_PUBLIC_ENABLE_DICEBEAR_AVATARS === '1';
const DICEBEAR_STYLE = process.env.NEXT_PUBLIC_DICEBEAR_STYLE ?? 'identicon';
const DICEBEAR_BASE = 'https://api.dicebear.com/9.x';

function normalizeSeed(seed: string): string {
    return seed.trim().toLowerCase().replace(/\s+/g, '-');
}

export function getModelAvatarUrl(modelName: string, customLogoUrl?: string): string | null {
    // Prioritize custom logo if provided
    if (customLogoUrl) return customLogoUrl;

    // Map known providers and models to static SVG logos
    const lower = (modelName || '').toLowerCase();

    // Anthropic / Claude
    if (lower.includes('claude') || lower.includes('anthropic')) {
        return '/logos/claude.svg';
    }
    // Google / Gemini
    if (lower.includes('gemini') || lower.includes('google')) {
        return '/logos/googlegemini.svg';
    }
    // OpenAI / GPT / o1 / o3
    if (lower.includes('gpt') || lower.includes('openai') || lower.includes('o1') || lower.includes('o3')) {
        return '/logos/openai.svg';
    }
    // Mistral
    if (lower.includes('mistral') || lower.includes('mixtral')) {
        return '/logos/mistralai.svg';
    }
    // Groq
    if (lower.includes('groq')) {
        return '/logos/groq.svg';
    }
    // OpenRouter (fallback / routing platform)
    if (lower.includes('openrouter')) {
        return '/logos/openrouter.svg';
    }

    // Fallback to DiceBear pattern
    if (!ENABLE_DICEBEAR_AVATARS) return null;
    const seed = normalizeSeed(modelName || 'unknown-model');
    return `${DICEBEAR_BASE}/${DICEBEAR_STYLE}/svg?seed=${encodeURIComponent(seed)}`;
}

export function getWorkspaceAvatarUrl(workspaceId: string): string | null {
    if (!ENABLE_DICEBEAR_AVATARS) return null;
    const seed = normalizeSeed(workspaceId || 'default-workspace');
    return `${DICEBEAR_BASE}/${DICEBEAR_STYLE}/svg?seed=${encodeURIComponent(seed)}`;
}
