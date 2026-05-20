/**
 * SSE client for streaming DM narrative from the backend.
 *
 * Connects to GET /api/game/stream?input=... and emits events for
 * streaming tokens, final narrative, NPC thinking, and completion.
 */
const SSEClient = {
    eventSource: null,

    /**
     * Open an SSE connection to stream the DM's response.
     *
     * @param {string} input - The player's action text.
     * @param {object} callbacks - Event callbacks.
     * @param {function} callbacks.onToken - Called with each streamed token.
     * @param {function} callbacks.onNarrative - Called with the final narrative.
     * @param {function} callbacks.onNpcThinking - Called with {npc_id, hint} on NPC processing.
     * @param {function} callbacks.onDone - Called with turn_count on completion.
     * @param {function} callbacks.onTokenUsage - Called with {usage: {prompt_tokens, completion_tokens, total_tokens}}.
     * @param {function} callbacks.onError - Called with an error message.
     */
    connect(input, provider, callbacks) {
        this.disconnect();

        let url = `/api/game/stream?input=${encodeURIComponent(input)}`;
        if (provider) {
            url += `&base_url=${encodeURIComponent(provider.base_url || '')}`;
            url += `&model=${encodeURIComponent(provider.model || '')}`;
            url += `&provider_type=${encodeURIComponent(provider.provider_type || 'ollama')}`;
            if (provider.api_key) {
                url += `&api_key=${encodeURIComponent(provider.api_key)}`;
            }
        }
        this.eventSource = new EventSource(url);

        this.eventSource.addEventListener("token", (e) => {
            try {
                const data = JSON.parse(e.data);
                if (callbacks.onToken) callbacks.onToken(data.content);
            } catch (_) { /* skip malformed events */ }
        });

        this.eventSource.addEventListener("narrative", (e) => {
            try {
                const data = JSON.parse(e.data);
                if (callbacks.onNarrative) callbacks.onNarrative(data.content);
            } catch (_) { /* skip malformed events */ }
        });

        this.eventSource.addEventListener("npc_thinking", (e) => {
            try {
                const data = JSON.parse(e.data);
                if (callbacks.onNpcThinking) callbacks.onNpcThinking(data);
            } catch (_) { /* skip malformed events */ }
        });

        this.eventSource.addEventListener("done", (e) => {
            try {
                const data = JSON.parse(e.data);
                if (callbacks.onDone) callbacks.onDone(data.turn_count);
            } catch (_) { /* skip malformed events */ }
            this.disconnect();
        });

        this.eventSource.addEventListener("token_usage", (e) => {
            try {
                const data = JSON.parse(e.data);
                if (callbacks.onTokenUsage) callbacks.onTokenUsage(data.usage);
            } catch (_) { /* skip malformed events */ }
        });

        this.eventSource.onerror = () => {
            if (callbacks.onError) callbacks.onError("Connection lost");
        };
    },

    /** Close the current SSE connection if any. */
    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    },
};
