import type {
    ConsultaionClientOptions,
    Debate,
    DebateCreateOptions,
    DebateEvent,
} from './types';

/**
 * Official Consultaion API client
 */
export class ConsultaionClient {
    private baseUrl: string;
    private apiKey?: string;
    private fetchFn: typeof fetch;

    constructor(options: ConsultaionClientOptions) {
        this.baseUrl = options.baseUrl.replace(/\/$/, ''); // Remove trailing slash
        this.apiKey = options.apiKey;
        this.fetchFn = options.fetch || (typeof fetch !== 'undefined' ? fetch : require('node-fetch'));
    }

    /**
     * Create a new debate
     */
    async createDebate(options: DebateCreateOptions): Promise<Debate> {
        const response = await this.fetchFn(`${this.baseUrl}/debates`, {
            method: 'POST',
            headers: this.getHeaders(),
            body: JSON.stringify(options),
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ message: response.statusText }));
            throw new Error(`Failed to create debate: ${error.message || response.statusText}`);
        }

        return response.json();
    }

    /**
     * Get a debate by ID
     */
    async getDebate(id: string): Promise<Debate> {
        const response = await this.fetchFn(`${this.baseUrl}/debates/${id}`, {
            method: 'GET',
            headers: this.getHeaders(),
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ message: response.statusText }));
            throw new Error(`Failed to get debate: ${error.message || response.statusText}`);
        }

        return response.json();
    }

    /**
     * Stream events from a debate (Server-Sent Events)
     * 
     * @param id - Debate ID
     * @param onEvent - Callback function for each event
     * @param onError - Optional error callback
     * @returns Cleanup function to stop streaming
     */
    streamEvents(
        id: string,
        onEvent: (event: DebateEvent) => void,
        onError?: (error: Error) => void
    ): () => void {
        const url = `${this.baseUrl}/debates/${id}/stream`;
        const headers = this.getHeaders();

        let controller: AbortController | undefined;
        let stopped = false;

        // Use EventSource if available (browser), otherwise fall back to fetch streaming
        if (typeof EventSource !== 'undefined') {
            // Browser environment
            const eventSource = new EventSource(url);

            eventSource.onmessage = (e) => {
                try {
                    const data = JSON.parse(e.data);
                    onEvent({ type: e.type || 'message', data });
                } catch (err) {
                    if (onError) onError(err as Error);
                }
            };

            eventSource.onerror = (err) => {
                if (!stopped && onError) {
                    onError(new Error('EventSource error'));
                }
                eventSource.close();
            };

            return () => {
                stopped = true;
                eventSource.close();
            };
        } else {
            // Node.js environment - use fetch streaming
            controller = new AbortController();

            (async () => {
                try {
                    const response = await this.fetchFn(url, {
                        method: 'GET',
                        headers,
                        signal: controller!.signal,
                    });

                    if (!response.ok) {
                        throw new Error(`Failed to stream events: ${response.statusText}`);
                    }

                    const reader = response.body?.getReader();
                    const decoder = new TextDecoder();

                    if (!reader) {
                        throw new Error('Response body is not readable');
                    }

                    while (!stopped) {
                        const { done, value } = await reader.read();
                        if (done) break;

                        const chunk = decoder.decode(value, { stream: true });
                        const lines = chunk.split('\n');

                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                try {
                                    const data = JSON.parse(line.slice(6));
                                    onEvent({ type: 'message', data });
                                } catch (err) {
                                    if (onError) onError(err as Error);
                                }
                            }
                        }
                    }
                } catch (err) {
                    if (!stopped && onError) {
                        onError(err as Error);
                    }
                }
            })();

            return () => {
                stopped = true;
                controller?.abort();
            };
        }
    }

    private getHeaders(): Record<string, string> {
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
        };

        if (this.apiKey) {
            headers['X-API-Key'] = this.apiKey;
        }

        return headers;
    }
}
