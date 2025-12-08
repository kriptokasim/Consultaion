export interface ModelDetail {
    id: string
    name: string
    provider: string
    strengths: string[]
    limitations: string[]
    bestFor: string[]
}

export const MODEL_DETAILS: Record<string, ModelDetail> = {
    'gpt-4o': {
        id: 'gpt-4o',
        name: 'GPT-4o',
        provider: 'OpenAI',
        strengths: [
            'Fast and versatile reasoning across domains',
            'Strong general knowledge and code generation',
            'Excellent at synthesizing complex information',
            'Balanced performance on most tasks'
        ],
        limitations: [
            'May be overly confident in uncertain scenarios',
            'Knowledge cutoff (no real-time web access)',
            'Can occasionally miss nuanced ethical considerations'
        ],
        bestFor: [
            'Broad strategy questions and planning',
            'Product and design ideation',
            'Technical problem-solving and code review',
            'General-purpose analytical tasks'
        ]
    },
    'claude-3.5': {
        id: 'claude-3.5',
        name: 'Claude 3.5 Sonnet',
        provider: 'Anthropic',
        strengths: [
            'Careful, nuanced reasoning with attention to detail',
            'Excellent with long-form analysis and documents',
            'Strong ethical considerations and safety awareness',
            'Superior at complex multi-step reasoning'
        ],
        limitations: [
            'Can be overly cautious or conservative',
            'Slower response time for complex queries',
            'May overexplain obvious concepts'
        ],
        bestFor: [
            'Policy analysis and compliance reviews',
            'Complex reasoning and philosophical questions',
            'Long document analysis and summarization',
            'Ethical dilemma evaluation'
        ]
    },
    'gemini-pro': {
        id: 'gemini-pro',
        name: 'Gemini Pro',
        provider: 'Google',
        strengths: [
            'Strong research capabilities and fact-finding',
            'Good at comparative analysis and benchmarking',
            'Multimodal understanding (text + other modalities)',
            'Access to up-to-date information patterns'
        ],
        limitations: [
            'Less established track record than competitors',
            'Variable performance on edge cases',
            'Can be verbose with explanations'
        ],
        bestFor: [
            'Research-heavy questions and investigations',
            'Comparative studies and feature analysis',
            'Data-driven decision support',
            'Market research and competitive intel'
        ]
    }
}
