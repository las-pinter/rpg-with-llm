/**
 * SSE client for streaming DM narrative from the backend.
 *
 * Connects to GET /api/game/stream?input=... and emits events for
 * streaming tokens, final narrative, NPC thinking, state updates,
 * token usage, and completion.
 */
const SSEClient = {
    eventSource: null,

    /**
     * Open an SSE connection to stream the DM's response.
     *
     * @param {string} input - The player's action text.
     * @param {object|null} provider - Main provider config.
     * @param {object} callbacks - Event callbacks.
     * @param {function} callbacks.onToken - Called with each streamed token.
     * @param {function} callbacks.onNarrative - Called with the final narrative.
     * @param {function} callbacks.onNpcThinking - Called with {npc_id, hint}.
     * @param {function} callbacks.onStateUpdate - Called with {state, turn_count}.
     * @param {function} callbacks.onTokenUsage - Called with {usage: ...}.
     * @param {function} callbacks.onDone - Called with turn_count.
     * @param {function} callbacks.onError - Called with error message.
     * @param {object|null} state - Current world state dict (for continuity).
     * @param {object|null} character - Current character dict.
     * @param {object|null} npcProvider - NPC provider config.
     * @param {object|null} summarizerProvider - Summarizer provider config.
     */
    connect(input, provider, callbacks, state, character, npcProvider, summarizerProvider) {
        this.disconnect();

        let url = `/api/game/stream?input=${encodeURIComponent(input)}`;

        // Main provider query params
        if (provider) {
            url += `&base_url=${encodeURIComponent(provider.base_url || '')}`;
            url += `&model=${encodeURIComponent(provider.model || '')}`;
            url += `&provider_type=${encodeURIComponent(provider.provider_type || 'ollama')}`;
            if (provider.api_key) {
                url += `&api_key=${encodeURIComponent(provider.api_key)}`;
            }
        }

        // NPC provider (separate agent)
        if (npcProvider && npcProvider.base_url && npcProvider.model) {
            url += `&npc_base_url=${encodeURIComponent(npcProvider.base_url)}`;
            url += `&npc_model=${encodeURIComponent(npcProvider.model)}`;
            url += `&npc_provider_type=${encodeURIComponent(npcProvider.provider_type || 'ollama')}`;
            if (npcProvider.api_key) {
                url += `&npc_api_key=${encodeURIComponent(npcProvider.api_key)}`;
            }
        }

        // Summarizer provider (separate agent)
        if (summarizerProvider && summarizerProvider.base_url && summarizerProvider.model) {
            url += `&summarizer_base_url=${encodeURIComponent(summarizerProvider.base_url)}`;
            url += `&summarizer_model=${encodeURIComponent(summarizerProvider.model)}`;
            url += `&summarizer_provider_type=${encodeURIComponent(summarizerProvider.provider_type || 'ollama')}`;
            if (summarizerProvider.api_key) {
                url += `&summarizer_api_key=${encodeURIComponent(summarizerProvider.api_key)}`;
            }
        }

        // World state (JSON-encoded for continuity)
        if (state) {
            url += `&state=${encodeURIComponent(JSON.stringify(state))}`;
        }

        // Character data (JSON-encoded)
        if (character) {
            url += `&character=${encodeURIComponent(JSON.stringify(character))}`;
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

        this.eventSource.addEventListener("state_update", (e) => {
            try {
                const data = JSON.parse(e.data);
                if (callbacks.onStateUpdate) callbacks.onStateUpdate(data);
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
