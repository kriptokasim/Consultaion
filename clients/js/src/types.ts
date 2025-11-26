/**
 * TypeScript interfaces for Consultaion API
 */

export interface DebateCreateOptions {
    /** The question or topic for the debate */
    prompt: string;

    /** Optional explicit model ID to use */
    model_id?: string;

    /** Optional routing policy: 'router-smart' or 'router-deep' */
    routing_policy?: 'router-smart' | 'router-deep';

    /** Optional debate configuration */
    config?: {
        agents?: Array<{
            name: string;
            persona: string;
            model?: string;
            tools?: string[];
        }>;
        judges?: Array<{
            name: string;
            model?: string;
            rubrics?: string[];
        }>;
    };
}

export interface Debate {
    id: string;
    prompt: string;
    status: 'queued' | 'running' | 'completed' | 'failed';
    created_at: string;
    updated_at?: string;
    user_id: string;
    model_id?: string;
    routed_model?: string;
    routing_policy?: string;
    routing_meta?: {
        candidates?: Array<{
            model: string;
            total_score: number;
            cost_score: number;
            latency_score: number;
            quality_score: number;
            safety_score: number;
            is_healthy: boolean;
        }>;
        requested_model?: string;
    };
    config?: Record<string, unknown>;
    error?: string;
}

export interface DebateEvent {
    type: string;
    data: Record<string, unknown>;
    timestamp?: string;
}

export interface ConsultaionClientOptions {
    /** Base URL for the API (e.g., 'https://api.consultaion.com') */
    baseUrl: string;

    /** API key for authentication */
    apiKey?: string;

    /** Custom fetch function (for testing or custom behavior) */
    fetch?: typeof fetch;
}
